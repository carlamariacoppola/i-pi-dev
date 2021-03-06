"""Contains the classes that deal with the normal mode representation.

Deals with the normal mode transformation, including the complications
introduced by PA-CMD when the bead masses are rescaled. Also deals with
the change in the dynamics introduced by this mass-scaling, and has its
own functions to calculate the kinetic energy, and the exact propagator
in the normal mode representation under the ring polymer Hamiltonian.
"""

# This file is part of i-PI.
# i-PI Copyright (C) 2014-2015 i-PI developers
# See the "licenses" directory for full license information.


import numpy as np

from ipi.utils.depend import *
from ipi.utils import units
from ipi.utils import nmtransform
from ipi.utils.messages import verbosity, warning, info


__all__ = [ "NormalModes" ]


class NormalModes(dobject):
   """Handles the path normal modes.

   Normal-modes transformation, determination of path frequencies,
   dynamical mass matrix change, etc.

   Attributes:
      natoms: The number of atoms.
      nbeads: The number of beads.
      beads: The beads object for which the normal mode transformation should
         be done.
      ensemble: The ensemble object, specifying the temperature to hold the
         system to.
      motion: The motion object that will need normal-mode transformation and propagator
      transform: A nm_trans object that contains the functions that are
         required for the normal mode transformation.

   Depend objects:
      mode: A string specifying how the bead masses are chosen.
      transform_method: A string specifying how to do the normal mode
         transformation.
      nm_freqs: An array that specifies how the normal mode frequencies
         of the ring polymers are to be calculated, and thus how the
         bead masses should be chosen.
      qnm: The bead positions in the normal mode representation. Depends on
         beads.q.
      pnm: The bead momenta in the normal mode representation. Depends on
         beads.p.
      omegan: The effective vibrational frequency for the interaction
         between the replicas. Depends on the simulation temperature.
      omegan2: omegan**2.
      omegak: The normal mode frequencies for the free ring polymer.
         Depends on omegan.
      prop_pq: An array holding the exact normal mode propagator for the
         free ring polymer, using mass scaled coordinates.
         See J. Chem. Phys. 133, 124101 (2010). Depends on the bead masses
         and the timestep.
      nm_factor: An array of dynamical mass factors associated with each of
         the normal modes. Depends on nm_freqs and mode.
      dynm3: An array that gives the dynamical masses of individual atoms in the
         normal modes representation. Depends on nm_factor and beads.m3.
      dynomegak: The scaled vibrational frequencies. Depends on nm_factor and
         omegak.
      kins: A list of the kinetic energy for each normal mode, as
         calculated in the normal mode representation, using the
         dynamical mass factors. Depends on beads.sm3, beads.p and nm_factor.
      kin: The total kinetic energy, as calculated in the normal mode
         representation, using the dynamical mass factors.
      kstress: The kinetic stress tensor, as calculated in the normal mode
         representation, using the dynamical mass factors. Depends on
         beads.sm3, beads.p and nm_factor.
   """

   def __init__(self, mode="rpmd", transform_method="fft", freqs=None, dt=1.0):
      """Initializes NormalModes.

      Sets the options for the normal mode transform.

      Args:
         mode: A string specifying how to calculate the bead masses.
         transform_method: A string specifying how to do the normal mode
            transformation.
         freqs: A list of data used to calculate the dynamical mass factors.
      """

      if freqs is None:
         freqs = []
      dset(self,"dt", depend_value(name='dt', value=dt))
      dset(self,"mode",   depend_value(name='mode', value=mode))
      dset(self,"transform_method",
         depend_value(name='transform_method', value=transform_method))
      dset(self,"nm_freqs",
         depend_array(name="nm_freqs",value=np.asarray(freqs, float) ) )

   def bind(self, ensemble, motion, beads=None, forces=None):
      """ Initializes the normal modes object and binds to beads and ensemble.

      Do all the work down here as we need a full-formed necklace and ensemble
      to know how this should be done.

      Args:
         beads: A beads object to be bound.
         ensemble: An ensemble object to be bound.
      """

      self.ensemble = ensemble
      self.motion = motion      
      if beads is None: 
        self.beads = motion.beads
      else:
        self.beads = beads
      self.forces = forces
      self.nbeads = beads.nbeads
      self.natoms = beads.natoms

      # stores a reference to the bound beads and ensemble objects
      self.ensemble = ensemble
      deppipe(motion, "dt", self, "dt")

      # sets up what's necessary to perform nm transformation.
      if self.transform_method == "fft":
         self.transform = nmtransform.nm_fft(nbeads=self.nbeads, natoms=self.natoms)
      elif self.transform_method == "matrix":
         self.transform = nmtransform.nm_trans(nbeads=self.nbeads)

      # creates arrays to store normal modes representation of the path.
      # must do a lot of piping to create "ex post" a synchronization between the beads and the nm
      sync_q = synchronizer()
      sync_p = synchronizer()
      dset(self,"qnm",
         depend_array(name="qnm",
            value=np.zeros((self.nbeads,3*self.natoms), float),
               func={"q": (lambda : self.transform.b2nm(depstrip(self.beads.q)) ) },
                  synchro=sync_q ) )
      dset(self,"pnm",
         depend_array(name="pnm",
            value=np.zeros((self.nbeads,3*self.natoms), float),
               func={"p": (lambda : self.transform.b2nm(depstrip(self.beads.p)) ) },
                  synchro=sync_p ) )

      # must overwrite the functions
      dget(self.beads, "q")._func = { "qnm": (lambda : self.transform.nm2b(depstrip(self.qnm)) )  }
      dget(self.beads, "p")._func = { "pnm": (lambda : self.transform.nm2b(depstrip(self.pnm)) )  }
      dget(self.beads, "q").add_synchro(sync_q)
      dget(self.beads, "p").add_synchro(sync_p)

      # also within the "atomic" interface to beads
      for b in range(self.nbeads):
         dget(self.beads._blist[b],"q")._func = { "qnm": (lambda : self.transform.nm2b(depstrip(self.qnm)) )  }
         dget(self.beads._blist[b],"p")._func = { "pnm": (lambda : self.transform.nm2b(depstrip(self.pnm)) )  }
         dget(self.beads._blist[b],"q").add_synchro(sync_q)
         dget(self.beads._blist[b],"p").add_synchro(sync_p)


      # finally, we mark the beads as those containing the set positions
      dget(self.beads, "q").update_man()
      dget(self.beads, "p").update_man()
      
      # forces can be converted in nm representation, but here it makes no sense to set up a sync mechanism, 
      # as they always get computed in the bead rep
      if not self.forces is None: dset(self,"fnm", depend_array(name="fnm",
         value=np.zeros((self.nbeads,3*self.natoms), float),func=(lambda : self.transform.b2nm(depstrip(self.forces.f)) ),    
            dependencies=[dget(self.forces,"f")] ) )
      else: # have a fall-back plan when we don't want to initialize a force mechanism, e.g. for ring-polymer initialization         
         dset(self,"fnm", depend_array(name="fnm",
         value=np.zeros((self.nbeads,3*self.natoms), float),
         func=(lambda: depraise(ValueError("Cannot access NM forces when initializing the NM object without providing a force reference!") ) ),    
            dependencies=[] ) )
         
      # create path-frequencies related properties
      dset(self,"omegan",
         depend_value(name='omegan', func=self.get_omegan,
            dependencies=[dget(self.ensemble,"temp")]) )
      dset(self,"omegan2", depend_value(name='omegan2',func=self.get_omegan2,
            dependencies=[dget(self,"omegan")]) )
      dset(self,"omegak", depend_array(name='omegak',
         value=np.zeros(self.beads.nbeads,float),
            func=self.get_omegak, dependencies=[dget(self,"omegan")]) )
      dset(self,"omegak2", depend_array(name='omegak2',
         value=np.zeros(self.beads.nbeads,float),
            func=(lambda: (self.omegak)**2), dependencies=[dget(self,"omegak")]) )
            
      # sets up "dynamical" masses -- mass-scalings to give the correct RPMD/CMD dynamics
      # TODO: Do we really need different names and variable names? Seems confusing.
      dset(self,"nm_factor", depend_array(name="nmm",
         value=np.zeros(self.nbeads, float), func=self.get_nmm,
            dependencies=[dget(self,"nm_freqs"), dget(self,"mode") ]) )
      dset(self,"dynm3", depend_array(name="dm3",
         value=np.zeros((self.nbeads,3*self.natoms), float),func=self.get_dynm3,
            dependencies=[dget(self,"nm_factor"), dget(self.beads, "m3")] ) )
      dset(self,"dynomegak", depend_array(name="dynomegak",
         value=np.zeros(self.nbeads, float), func=self.get_dynwk,
            dependencies=[dget(self,"nm_factor"), dget(self,"omegak") ]) )

      dset(self, "dt", depend_value(name="dt", value = 1.0) )
      deppipe(self.motion, "dt", self, "dt")
      dset(self,"prop_pq",
         depend_array(name='prop_pq',value=np.zeros((self.beads.nbeads,2,2)),
            func=self.get_prop_pq,
               dependencies=[dget(self,"omegak"), dget(self,"nm_factor"), dget(self,"dt")]) )

      # if the mass matrix is not the RPMD one, the MD kinetic energy can't be
      # obtained in the bead representation because the masses are all mixed up
      dset(self,"kins",
         depend_array(name="kins",value=np.zeros(self.nbeads, float),
            func=self.get_kins,
               dependencies=[dget(self,"pnm"), dget(self.beads,"sm3"), dget(self, "nm_factor") ] ))
      dset(self,"kin",
         depend_value(name="kin", func=self.get_kin,
            dependencies=[dget(self,"kins")] ))
      dset(self,"kstress",
         depend_array(name="kstress",value=np.zeros((3,3), float),
            func=self.get_kstress,
               dependencies=[dget(self,"pnm"), dget(self.beads,"sm3"), dget(self, "nm_factor") ] ))

      # spring energy, calculated in normal modes
      dset(self, "vspring",
         depend_value(name="vspring",
            value=0.0,
            func=self.get_vspring,
            dependencies=[dget(self, "qnm"), dget(self, "omegak"), dget(self.beads, "m3")]))

      # spring forces on normal modes
      dset(self, "fspringnm",
         depend_array(name="fspringnm",
            value=np.zeros((self.nbeads, 3*self.natoms), float),
            func=self.get_fspringnm,
            dependencies=[dget(self, "qnm"), dget(self, "omegak"), dget(self.beads, "m3")]))

      # spring forces on beads, transformed from normal modes
      dset(self,"fspring",
         depend_array(name="fs",
            value=np.zeros((self.nbeads,3*self.natoms), float),
            func=(lambda: self.transform.nm2b(depstrip(self.fspringnm))),
            dependencies = [dget(self, "fspringnm")]))


   def get_fspringnm(self):
      """Returns the spring force calculated in NM representation."""

      return - self.beads.m3 * self.omegak[:,np.newaxis]**2 * self.qnm

   def get_vspring(self):
      """Returns the spring energy calculated in NM representation."""

      return 0.5 * (self.beads.m3 * self.omegak[:,np.newaxis]**2 * self.qnm**2).sum()

   def get_omegan(self):
      """Returns the effective vibrational frequency for the interaction
      between replicas.
      """

      return self.ensemble.temp*self.nbeads*units.Constants.kb/units.Constants.hbar

   def get_omegan2(self):
      """Returns omegan**2."""

      return self.omegan**2

   def get_omegak(self):
      """Gets the normal mode frequencies.

      Returns:
         A list of the normal mode frequencies for the free ring polymer.
         The first element is the centroid frequency (0.0).
      """

      return 2*self.omegan*np.array([np.sin(k*np.pi/self.nbeads) for k in range(self.nbeads)])

   def get_dynwk(self):
      """Gets the dynamical normal mode frequencies.

      Returns:
         A list of the scaled normal mode frequencies for the free ring polymer.
         The first element is the centroid frequency (0.0).
      """

      return self.omegak/np.sqrt(self.nm_factor)

   def get_prop_pq(self):
      """Gets the normal mode propagator matrix.

      Note the special treatment for the centroid normal mode, which is
      propagated using the standard velocity Verlet algorithm as required.
      Note that both the normal mode positions and momenta are propagated
      using this matrix.

      Returns:
         An array of the form (nbeads, 2, 2). Each 2*2 array prop_pq[i,:,:]
         gives the exact propagator for the i-th normal mode of the
         ring polymer.
      """

      dt = self.dt
      pqk = np.zeros((self.nbeads,2,2), float)
      pqk[0] = np.array([[1,0], [dt,1]])

      # Note that the propagator uses mass-scaled momenta.
      for b in range(1, self.nbeads):
         sk = np.sqrt(self.nm_factor[b])

         dtomegak = self.omegak[b]*dt/sk
         c = np.cos(dtomegak)
         s = np.sin(dtomegak)
         pqk[b,0,0] = c
         pqk[b,1,1] = c
         pqk[b,0,1] = -s*self.omegak[b]*sk
         pqk[b,1,0] = s/(self.omegak[b]*sk)

      return pqk

   def get_nmm(self):
      """Returns dynamical mass factors, i.e. the scaling of normal mode
      masses that determine the path dynamics (but not statics)."""

      # also checks that the frequencies and the mode given in init are
      # consistent with the beads and ensemble

      dmf = np.ones(self.nbeads, float)
      if self.mode == "rpmd":
         if len(self.nm_freqs) > 0:
            warning("nm.frequencies will be ignored for RPMD mode.", verbosity.low)
      elif self.mode == "manual":
         if len(self.nm_freqs) != self.nbeads-1:
            raise ValueError("Manual path mode requires (nbeads-1) frequencies, one for each internal mode of the path.")
         for b in range(1, self.nbeads):
            sk = self.omegak[b]/self.nm_freqs[b-1]
            dmf[b] = sk**2
      elif self.mode == "pa-cmd":
         if len(self.nm_freqs) > 1:
            warning("Only the first element in nm.frequencies will be considered for PA-CMD mode.", verbosity.low)
         if len(self.nm_freqs) == 0:
            raise ValueError("PA-CMD mode requires the target frequency of all the internal modes.")
         for b in range(1, self.nbeads):
            sk = self.omegak[b]/self.nm_freqs[0]
            info(" ".join(["NM FACTOR", str(b), str(sk), str(self.omegak[b]), str(self.nm_freqs[0])]), verbosity.medium)
            dmf[b] = sk**2
      elif self.mode == "wmax-cmd":
         if len(self.nm_freqs) > 2:
            warning("Only the first two element in nm.frequencies will be considered for WMAX-CMD mode.", verbosity.low)
         if len(self.nm_freqs) < 2:
            raise ValueError("WMAX-CMD mode requires [wmax, wtarget]. The normal modes will be scaled such that the first internal mode is at frequency wtarget and all the normal modes coincide at frequency wmax.")
         wmax = self.nm_freqs[0]
         wt = self.nm_freqs[1]
         for b in range(1, self.nbeads):
            sk = 1.0/np.sqrt((wt)**2*(1+(wmax/self.omegak[1])**2)/(wmax**2+(self.omegak[b])**2))
            dmf[b] = sk**2

      return dmf

   def get_dynm3(self):
      """Returns an array with the dynamical masses of individual atoms in the normal modes representation."""

      dm3 = np.zeros(self.beads.m3.shape,float)
      for b in range(self.nbeads):
         dm3[b] = self.beads.m3[b]*self.nm_factor[b]

      return dm3

   def free_qstep(self):
      """Exact normal mode propagator for the free ring polymer.

      Note that the propagator works in mass scaled coordinates, so that the
      propagator matrix can be determined independently from the particular
      atom masses, and so the same propagator will work for all the atoms in
      the system. All the ring polymers are propagated at the same time by a
      matrix multiplication.

      Also note that the centroid coordinate is propagated in qcstep, so is
      not altered here.
      """

      if self.nbeads == 1:
         pass
      else:
         pq = np.zeros((2,self.natoms*3),float)         
         sm = depstrip(self.beads.sm3)
         prop_pq = depstrip(self.prop_pq) 
         pnm = depstrip(self.pnm)/sm
         qnm = depstrip(self.qnm)*sm
         
         for k in range(1,self.nbeads):
            pq[0,:] = pnm[k]
            pq[1,:] = qnm[k]
            pq = np.dot(prop_pq[k],pq)
            qnm[k] = pq[1,:]
            pnm[k] = pq[0,:]
         self.pnm = pnm * sm
         self.qnm = qnm / sm
         #pq = np.zeros((2,self.natoms*3),float)
         #sm = depstrip(self.beads.sm3)[0]
         #prop_pq = depstrip(self.prop_pq)
         #for k in range(1,self.nbeads):
         #   pq[0,:] = depstrip(self.pnm)[k]/sm
         #   pq[1,:] = depstrip(self.qnm)[k]*sm
         #   pq = np.dot(prop_pq[k],pq)
         #   self.qnm[k] = pq[1,:]/sm
         #   self.pnm[k] = pq[0,:]*sm

   def get_kins(self):
      """Gets the MD kinetic energy for all the normal modes.

      Returns:
         A list of the kinetic energy for each NM.
      """

      kmd = np.zeros(self.nbeads,float)
      sm = depstrip(self.beads.sm3[0])
      pnm = depstrip(self.pnm)
      nmf = depstrip(self.nm_factor)

      # computes the MD ke in the normal modes representation, to properly account for CMD mass scaling
      for b in range(self.nbeads):
         sp = pnm[b]/sm                      # mass-scaled momentum of b-th NM
         kmd[b] = np.dot(sp,sp)*0.5/nmf[b]   # include the partially adiabatic CMD mass scaling

      return kmd

   def get_kin(self):
      """Gets the total MD kinetic energy.

      Note that this does not correspond to the quantum kinetic energy estimate
      for the system.

      Returns:
         The sum of the kinetic energy of each NM in the path.
      """

      return self.kins.sum()

   def get_kstress(self):
      """Calculates the total MD kinetic stress tensor.

      Note that this does not correspond to the quantum kinetic stress tensor
      estimate for the system.

      Returns:
         The sum of the MD kinetic stress tensor contributions from each NM.
      """

      kmd = np.zeros((3,3),float)
      sm = depstrip(self.beads.sm3[0])
      pnm = depstrip(self.pnm)
      nmf = depstrip(self.nm_factor)

      for b in range(self.nbeads):
         sp = pnm[b]/sm  # mass-scaled momentum of b-th NM

         for i in range(3):
            for j in range(3):
               # computes the outer product of the p of various normal modes
               # singling out Cartesian components to build the tensor
               # also takes care of the possibility of having non-RPMD masses
               kmd[i,j] += np.dot(sp[i:3*self.natoms:3],sp[j:3*self.natoms:3])/nmf[b]

      return kmd
