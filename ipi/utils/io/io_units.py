"""Functions used to transform units in input files into default atomic system of units.
"""

# This file is part of i-PI.
# i-PI Copyright (C) 2014-2015 i-PI developers
# See the "licenses" directory for full license information.


import re
from ipi.engine.atoms import Atoms
from ipi.engine.cell import Cell
from ipi.utils.units import unit_to_internal
from ipi.engine.properties import Trajectories as Traj


# Regular expressions initialization for read_xyz function
cell_unit_re = re.compile(r'cell\{([A-Za-z_]*)\}')       # cell unit pattern
traj_dict = Traj().traj_dict                             # trajectory dictionary
traj_re = [re.compile('%s%s' % (key, r'\{[A-Za-z_]*\}'))
           for key in traj_dict.keys()]  # trajectory patterns


def process_units(comment, cell, qatoms, names, masses, output='objects'):
    """Convert the data in the file according to the units written in the i-PI format.

    Args:
        comment:
        cell:
        qatoms:
        names:
        masses:
        output:

    Returns:

    """
    
    if comment == "" and output != 'objects': # fast mode
        return {
          "data": qatoms,
          "masses": masses,
          "names": names,
          "natoms": len(names),
          "cell": cell,
        }

    # Extracting trajectory units
    family, unit = 'undefined', ''
    is_comment_useful = filter(None, [key.search(comment.strip())
                                      for key in traj_re])
    if len(is_comment_useful) > 0:
        traj = is_comment_useful[0].group()[:-1].split('{')
        family, unit = traj_dict[traj[0]]['dimension'], traj[1]

    # Extracting cell units
    cell_unit = ''
    tmp = cell_unit_re.search(comment)
    if tmp is not None:
        cell_unit = tmp.group(1)

    # Units transformation
    cell *= unit_to_internal('length', cell_unit, 1) # cell units transformation
    qatoms *= unit_to_internal(family, unit, 1) # units transformation

    # return either objects or a raw data
    if output == 'objects':

        cell = Cell(cell)
        atoms = Atoms(len(names))
        atoms.q[:] = qatoms
        atoms.names[:] = names
        atoms.m[:] = masses

        return {
          "atoms": atoms,
          "cell": cell,
        }

    else:

        return {
          "data": qatoms,
          "masses": masses,
          "names": names,
          "natoms": len(names),
          "cell": cell,
        }
