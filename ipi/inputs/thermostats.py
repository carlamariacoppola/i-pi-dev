"""Creates objects that deal with constant temperature simulations.

Chooses between the different possible thermostat options and creates the
appropriate thermostat object, with suitable parameters.
"""

# This file is part of i-PI.
# i-PI Copyright (C) 2014-2015 i-PI developers
# See the "licenses" directory for full license information.


from copy import copy

import numpy as np

import ipi.engine.thermostats as ethermostats
from ipi.utils.depend   import *
from ipi.utils.inputvalue  import *


__all__ = ['InputThermo']


class InputThermoBase(Input):
   """Thermostat input class.

   Handles generating the appropriate thermostat class from the xml input file,
   and generating the xml checkpoiunt tags and data from an instance of the
   object.

   Attributes:
      mode: An optional string giving the type of the thermostat used. Defaults
         to 'langevin'.

   Fields:
      ethermo: An optional float giving the amount of heat energy transferred
         to the bath. Defaults to 0.0.
      tau: An optional float giving the damping time scale. Defaults to 1.0.
      invar: Sets the estimated variance of the inherent noise term. Defaults to 0.0.
      invtau: Coupling time coefficient for automatic adjustment of invar. Defaults to 0.0.
      pile_lambda: Scaling for the PILE damping relative to the critical damping.
      A: An optional array of floats giving the drift matrix. Defaults to 0.0.
      C: An optional array of floats giving the static covariance matrix.
         Defaults to 0.0.
      s: An optional array of floats giving the additional momentum-scaled
         momenta in GLE. Defaults to 0.0.
   """

   attribs = { "mode": (InputAttribute, { "dtype"   : str,
                                      "options" : [ "", "langevin", "nfl", "svr", "pile_l", "pile_g", "gle", "nm_gle", "nm_gle_g" ],
                                      "help"    : "The style of thermostatting. 'langevin' specifies a white noise langevin equation to be attached to the cartesian representation of the momenta. 'nfl' represents a modified langevin thermostat which compensates for additional white noise from noisy forces. 'svr' attaches a velocity rescaling thermostat to the cartesian representation of the momenta. Both 'pile_l' and 'pile_g' attaches a white noise langevin thermostat to the normal mode representation, with 'pile_l' attaching a local langevin thermostat to the centroid mode and 'pile_g' instead attaching a global velocity rescaling thermostat. 'gle' attaches a coloured noise langevin thermostat to the cartesian representation of the momenta, 'nm_gle' attaches a coloured noise langevin thermostat to the normal mode representation of the momenta and a langevin thermostat to the centroid and 'nm_gle_g' attaches a gle thermostat to the normal modes and a svr thermostat to the centroid.  'multiple' is a special thermostat mode, in which one can define multiple thermostats _inside_ the thermostat tag."
                                         }) }
   fields = { "ethermo" : (InputValue, {  "dtype"     : float,
                                          "default"   : 0.0,
                                          "help"      : "The initial value of the thermostat energy. Used when the simulation is restarted to guarantee continuity of the conserved quantity.",
                                          "dimension" : "energy" }),
            "tau" : (InputValue, {  "dtype"     : float,
                                    "default"   : 0.0,
                                    "help"      : "The friction coefficient for white noise thermostats.",
                                    "dimension" : "time" }),
            "invar" : (InputValue, {"dtype"     : float,
                                    "default"   : 0.0,
                                    "help"      : "The inherent noise variance for noisy force langevin thermostats.",
                                    "dimension" : "energy" }),
            "invtau" : (InputValue, {"dtype"    : float,
                                    "default"   : 0.0,
                                    "help"      : "The time coefficient for adjustment of NFL thermostat's invar.",
                                    "dimension" : "time" }),
            "pile_lambda" : (InputValue, { "dtype" : float,
                                    "default"   : 1.0,
                                    "help"      : "Scaling for the PILE damping relative to the critical damping. (gamma_k=2*lambda*omega_k"} ),
            "A" : (InputArray, {    "dtype"     : float,
                                    "default"   : input_default(factory=np.zeros, args = (0,)),
                                    "help"      : "The friction matrix for GLE thermostats.",
                                    "dimension" : "frequency" }),
            "C" : (InputArray, {    "dtype"     : float,
                                    "default"   : input_default(factory=np.zeros, args = (0,)),
                                    "help"      : "The covariance matrix for GLE thermostats.",
                                    "dimension" : "temperature" }),
            "s" : (InputArray, {    "dtype"     : float,
                                    "default"   : input_default(factory=np.zeros, args = (0,)),
                                    "help"      : "Input values for the additional momenta in GLE.",
                                    "dimension" : "ms-momentum" })
             }

   dynamic = {}

   default_help = "Simulates an external heat bath to keep the velocity distribution at the correct temperature."
   default_label = "THERMOSTATS"

   def store(self, thermo):
      """Takes a thermostat instance and stores a minimal representation of it.

      Args:
         thermo: A thermostat object.

      Raises:
         TypeError: Raised if the thermostat is not a recognized type.
      """

      super(InputThermoBase,self).store(thermo)
      if type(thermo) is ethermostats.ThermoLangevin:
         self.mode.store("langevin")
         self.tau.store(thermo.tau)
      elif type(thermo) is ethermostats.ThermoNFL:
         self.mode.store("nfl")
         self.tau.store(thermo.tau)
         self.invar.store(thermo.invar)
         self.invtau.store(thermo.invtau)
      elif type(thermo) is ethermostats.ThermoSVR:
         self.mode.store("svr")
         self.tau.store(thermo.tau)
      elif type(thermo) is ethermostats.ThermoPILE_L:
         self.mode.store("pile_l")
         self.tau.store(thermo.tau)
         self.pile_lambda.store(thermo.pilescale)
      elif type(thermo) is ethermostats.ThermoPILE_G:
         self.mode.store("pile_g")
         self.tau.store(thermo.tau)
         self.pile_lambda.store(thermo.pilescale)
      elif type(thermo) is ethermostats.ThermoGLE:
         self.mode.store("gle")
         self.A.store(thermo.A)
         if dget(thermo,"C")._func is None:
            self.C.store(thermo.C)
         self.s.store(thermo.s)
      elif type(thermo) is ethermostats.ThermoNMGLE:
         self.mode.store("nm_gle")
         self.A.store(thermo.A)
         if dget(thermo,"C")._func is None:
            self.C.store(thermo.C)
         self.s.store(thermo.s)
      elif type(thermo) is ethermostats.ThermoNMGLEG:
         self.mode.store("nm_gle_g")
         self.A.store(thermo.A)
         self.tau.store(thermo.tau)
         if dget(thermo,"C")._func is None:
            self.C.store(thermo.C)
         self.s.store(thermo.s)
      elif type(thermo) is ethermostats.Thermostat:
         self.mode.store("")
      else:
         raise TypeError("Unknown thermostat mode " + type(thermo).__name__)
      self.ethermo.store(thermo.ethermo)

   def fetch(self):
      """Creates a thermostat object.

      Returns:
         A thermostat object of the appropriate type and with the appropriate
         parameters given the attributes of the InputThermo object.

      Raises:
         TypeError: Raised if the thermostat type is not a recognized option.
      """

      super(InputThermoBase,self).fetch()
      if self.mode.fetch() == "langevin":
         thermo = ethermostats.ThermoLangevin(tau=self.tau.fetch())
      elif self.mode.fetch() == "nfl":
         thermo = ethermostats.ThermoNFL(tau=self.tau.fetch(), invar=self.invar.fetch(), invtau=self.invtau.fetch())
      elif self.mode.fetch() == "svr":
         thermo = ethermostats.ThermoSVR(tau=self.tau.fetch())
      elif self.mode.fetch() == "pile_l":
         thermo = ethermostats.ThermoPILE_L(tau=self.tau.fetch(), scale=self.pile_lambda.fetch())
      elif self.mode.fetch() == "pile_g":
         thermo = ethermostats.ThermoPILE_G(tau=self.tau.fetch(), scale=self.pile_lambda.fetch())
      elif self.mode.fetch() == "gle":
         rC = self.C.fetch()
         if len(rC) == 0:
            rC = None
         thermo = ethermostats.ThermoGLE(A=self.A.fetch(),C=rC)
         thermo.s = self.s.fetch()
      elif self.mode.fetch() == "nm_gle":
         rC = self.C.fetch()
         if len(rC) == 0:
            rC = None
         thermo = ethermostats.ThermoNMGLE(A=self.A.fetch(),C=rC)
         thermo.s = self.s.fetch()
      elif self.mode.fetch() == "nm_gle_g":
         rC = self.C.fetch()
         if len(rC) == 0:
            rC = None
         thermo = ethermostats.ThermoNMGLEG(A=self.A.fetch(),C=rC, tau=self.tau.fetch())
         thermo.s = self.s.fetch()
      elif self.mode.fetch() == "" :
         thermo=ethermostats.Thermostat()
      else:
         raise TypeError("Invalid thermostat mode " + self.mode.fetch())

      thermo.ethermo = self.ethermo.fetch()

      return thermo

   def check(self):
      """Checks that the parameter arrays represents a valid thermostat."""

      super(InputThermoBase,self).check()

      if self.mode.fetch() in ["langevin", "svr", "pile_l", "pile_g", "nm_gle_g"]:
         if self.tau.fetch() <= 0:
            raise ValueError("The thermostat friction coefficient must be set to a positive value")
      if self.mode.fetch() in ["nfl"]:
         if self.tau.fetch() < 0:
            raise ValueError("The thermostat friction coefficient must be set to a non-negative value")
         if self.invar.fetch() < 0:
            raise ValueError("The inherent noise variance must be set to a non-negative value")
         if self.invtau.fetch() < 0:
            raise ValueError("The automatic invar adjustment coefficient must be set to a non-negative value")
      if self.mode.fetch() in ["gle", "nm_gle", "nm_gle_g"]:
         pass  # PERHAPS DO CHECKS THAT MATRICES SATISFY REASONABLE CONDITIONS (POSITIVE-DEFINITENESS, ETC)


class InputThermo(InputThermoBase):
   """ Extends InputThermoBase to allow the definition of a multithermo """

   attribs = copy(InputThermoBase.attribs)

   attribs["mode"][1]["options"].append("multi")

   dynamic = { "thermostat" : (InputThermoBase, {"default"   : input_default(factory=ethermostats.Thermostat),
                                         "help"      : "The thermostat for the atoms, keeps the atom velocity distribution at the correct temperature."} )
             }

   def store(self, thermo):

      if type(thermo) is ethermostats.MultiThermo:
         self.mode.store("multi" )
         for t in thermo.tlist:
            it=InputThermoBase()
            it.store(t)
            self.extra.append(("thermostat",it))
         self.ethermo.store(thermo.ethermo)
      else:
          super(InputThermo,self).store(thermo)

   def fetch(self):

      if self.mode.fetch() == "multi" :
         tlist = []
         for (k, t) in self.extra:
            tlist.append(t.fetch())
         thermo=ethermostats.MultiThermo(thermolist=tlist)
         thermo.ethermo = self.ethermo.fetch()
      else:
         thermo=super(InputThermo,self).fetch()

      return thermo
