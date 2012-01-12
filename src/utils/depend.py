"""Contains the classes that are used to define the dependency network.

The classes defined in this module overload the standard __get__ and __set__
routines of the numpy ndarray class and standard library object class so that 
they automatically keep track of whether anything they depend on has been
altered, and so only recalculate their value when necessary. 

Basic quantities that depend on nothing else can be manually altered in the 
usual way, all other quantities are updated automatically and cannot be changed 
directly. 

The exceptions to this are synchronized properties, which are in effect 
multiple basic quantities all related to each other, for example the bead and
normal mode representations of the positions and momenta. In this case any of
the representations can be set manually, and all the other representations
must keep in step.

For a more detailed discussion, see the reference manual.

Classes:
   depend_base: Base depend class with the generic methods and attributes.
   depend_value: Depend class for scalar objects.
   depend_array: Depend class for arrays.
   synchronizer: Class that holds the different objects that are related to each
      other and keeps track of which property has been set manually.
   dobject: An extension of the standard library object that overloads 
      __getattribute__ and __setattribute__, so that we can use the 
      standard syntax for setting and getting the depend object, 
      i.e. foo = value, not foo.set(value).

Functions:
   dget: Gets the dependencies of a depend object.
   dset: Sets the dependencies of a depend object.
   depstrip: Used on a depend_array object, to access its value without
      needing the depend machinery, and so much more quickly. Must not be used
      if the value of the array is to be changed.
   depcopy: Copies the dependencies from one object to another
   deppipe: Used to make two objects be synchronized to the same value.
"""

__all__ = ['depend_base', 'depend_value', 'depend_array', 'synchronizer', 
           'dobject', 'dget', 'dset', 'depstrip', 'depcopy', 'deppipe']

import numpy as np

class synchronizer(object):
   """Class to implement synched objects.

   Holds the objects used to keep two or more objects in step with each other. 
   This is shared between all the synched objects.

   Attributes:
      synched: A dictionary containing all the synched objects, of the form
         {"name": depend object}.
      manual: A string containing the name of the object being manually changed.
   """

   def __init__(self, deps=None):
      """Initialises synchronizer.

      Args:
         deps: Optional dictionary giving the synched objects of the form
            {"name": depend object}.
      """

      if deps is None:
         self.synced=dict()
      else:
         self.synced=deps
         
      self.manual=None


#TODO put some error checks in the init to make sure that the object is initialized from consistent synchro and func states
class depend_base(object):
   """Base class for dependency handling.

   Builds the majority of the machinery required for the different depend
   objects. Contains functions to add and remove dependencies, the tainting 
   mechanism by which information about which objects have been updated is
   passed around the dependency network, and the manual and automatic update
   functions to check that depend objects with functions are not manually
   updated and that synchronized objects are kept in step with the one manually
   changed.

   Attributes:
      _tainted: An array containing one boolean, which is True if one of the
         dependencies has been changed since the last time the value was 
         cached.
      _func: A function name giving the method of calculating the value, 
         if required. None otherwise.
      _name: The name of the depend base object.
      _synchro: A synchronizer object to deal with synched objects, if
         required. None otherwise.
      _dependants: A list containing all objects dependent on the self.
   """ 

   def __init__(self, name, synchro=None, func=None, dependants=None, dependencies=None, tainted=None):
      """Initialises depend_base.

      An unusual initialisation routine, as it has to be able to deal with the
      depend array mechanism for returning slices as new depend arrays.

      This is the reason for the penultimate if statement; it automatically
      taints objects created from scratch but does nothing to slices which are
      not tainted.

      Also, the last if statement makes sure that if a synchronized property is
      sliced, this initialization routine does not automatically set it to the
      manually updated property.

      Args:
         name: A string giving the name of self.
         tainted: An optional array containing one boolean which is True if one
         of the dependencies has been changed.
         func: An optional argument that can be specified either by a function 
            name, or for synchronized values a dictionary of the form 
            {"name": function name}; where "name" is one of the other
            synched objects and function name is the name of a function to
            get the object "name" from self.
         synchro: An optional synchronizer object.
         dependants: An optional list containing objects that depend on self.
         dependencies: An optional list containing objects that self 
            depends upon.
      """

      self._dependants=[]
      if tainted is None:
         tainted=np.array([True],bool)
      if dependants is None:
         dependants=[]
      if dependencies is None:
         dependencies=[]
      self._tainted=tainted
      self._func=func
      self._name=name
      self._synchro=synchro
         
      for item in dependencies:
         item.add_dependant(self, tainted)
      
      self._dependants=dependants
      if (tainted): 
         self.taint(taintme=tainted)

      if not self._synchro is None and not self._name in self._synchro.synced:
         self._synchro.synced[self._name]=self
         self._synchro.manual=self._name
   
   def remove_dependant(self, rmdep):
      """Removes a dependency.

      Args:
         rmdep: The depend object to be removed from the dependency list.
      """

      irm=-1
      for idep in range(len(self._dependants)): 
         if self._dependants[idep] is rmdep: 
            irm=idep
      if irm >=0: 
         self._dependants.pop(irm)
      #self._dependants = [dep for dep in self._dependants if dep is not rmdep]
      #self._dependants.remove(rmdep)
         
   def add_dependant(self, newdep, tainted=True):
      """Adds a dependant property.

      Args:
         newdep: The depend object to be added to the dependency list.
         tainted: A boolean that decides whether newdep should be tainted.
            True by default.
      """

      self._dependants.append(newdep)
      if tainted: 
         newdep.taint(taintme=True)      

   def add_dependency(self, newdep, tainted=True):
      """Adds a dependency.

      Args:
         newdep: The depend object self now depends upon.
         tainted: A boolean that decides whether self should 
            be tainted. True by default.
      """

      newdep._dependants.append(self)      
      if tainted: 
         self.taint(taintme=True)

   def taint(self,taintme=True):
      """Recursively sets tainted flag on dependent objects.

      The main function dealing with the dependencies. Taints all objects 
      further down the dependency tree until either all objects have been
      tainted, or it reaches only objects that have already been tainted. Note
      that in the case of a dependency loop the initial setting of _tainted to
      True prevents an infinite loop occuring.

      Also, in the case of a synchro object, the manually set quantity is not
      tainted, as it is assumed that synchro objects only depend on each other.

      Args:
         taintme: A boolean giving whether self should be tainted at the end.
            True by default.
      """

      self._tainted[:] = True
      for item in self._dependants: 
         if (not item.tainted()):
            item.taint()
      if not self._synchro is None:
         for v in self._synchro.synced.values():
            if (not v.tainted()) and (not v is self):
               v.taint(taintme=True)
         self._tainted[:]=(taintme and (not self._name == self._synchro.manual))         
      else: self._tainted[:] = taintme
      
   def tainted(self):
      """Returns tainted flag."""

      return self._tainted[0]
      
   def update_auto(self):
      """Automatic update routine.

      Updates the value when get has been called and self has been tainted.
      """

      if not self._synchro is None:
         if (not self._name == self._synchro.manual):
            self.set(self._func[self._synchro.manual](), manual=False)
         else:
            print "####"+self._name+" probably shouldn't be tainted (synchro)!"
      elif not self._func is None: 
         self.set(self._func(), manual=False)
      else: 
         print "####"+self._name+" probably shouldn't be tainted (value)!"

   def update_man(self): 
      """Manual update routine.

      Updates the value when the value has been manually set. Also raises an
      exception if a calculated quantity has been manually set. Also starts the
      tainting routine.

      Raises:
         NameError: If a calculated quantity has been manually set.
      """

      if not self._synchro is None:     
         self._synchro.manual=self._name
         for v in self._synchro.synced.values():
            v.taint(taintme=True)
         self._tainted[:]=False      
      elif not self._func is None:
         raise NameError("Cannot set manually the value of the automatically-computed property <"+self._name+">")
      else:
         self.taint(taintme=False)     
            
   def set(self, value, manual=False):
      """Dummy setting routine."""

      pass           

   def get(self):      
      """Dummy getting routine."""

      pass


class depend_value(depend_base):
   """Scalar class for dependency handling.

   Attributes:
      _value: The value associated with self.
   """ 

   def __init__(self, name, value=None, synchro=None, func=None, dependants=None, dependencies=None, tainted=None):
      """Initialises depend_value.

      Args:
         name: A string giving the name of self.
         value: The value of the object. Optional.
         tainted: An optional array giving the tainted flag. Default is [True].
         func: An optional argument that can be specified either by a function 
            name, or for synchronized values a dictionary of the form 
            {"name": function name}; where "name" is one of the other
            synched objects and function name is the name of a function to
            get the object "name" from self.
         synchro: An optional synchronizer object.
         dependants: An optional list containing objects that depend on self.
         dependencies: An optional list containing objects that self 
            depends upon.
      """

      self._value=value
      super(depend_value,self).__init__(name, synchro, func, dependants, dependencies, tainted)

   def get(self):
      """Returns value, after recalculating if necessary.

      Overwrites the standard method of getting value, so that value
      is recalculated if tainted.
      """

      if self.tainted():  
         self.update_auto()
         self.taint(taintme=False)
         
      return self._value
      
   def __get__(self, instance, owner):
      """Overwrites standard get function."""

      return self.get() 

   def set(self, value, manual=True):
      """Alters value and taints dependencies.

      Overwrites the standard method of setting value, so that dependent 
      quantities are tainted, and so we check that computed quantities are not
      manually updated.
      """

      self._value=value
      self.taint(taintme=False)
      if (manual):
         self.update_man()
      
   def __set__(self, instance, value): 
      """Overwrites standard set function."""

      self.set(value)   


class depend_array(np.ndarray, depend_base):
   """Array class for dependency handling.

   Differs from depend_value as arrays handle getting items in a different
   way to scalar quantities, and as there needs to be support for slicing an
   array. Initialisation is also done in a different way for ndarrays.

   Attributes:
      _storage: The base array. Equal to value unless self is a slice.
   """

   def __new__(cls, value, name, synchro=None, func=None, dependants=None, dependencies=None, tainted=None, storage=None):
      """Creates a new array from a template.

      Called whenever a new instance of depend_array is created. Casts the
      array base into an appropriate form before passing it to 
      __array_finalize__().

      Args:
         See __init__().
      """

      obj = np.asarray(value).view(cls)
      return obj

   def __init__(self, value, name, synchro=None, func=None, dependants=None, dependencies=None, tainted=None, storage=None):
      """Initialises depend_array.

      Note that this is only called when a new array is created by an 
      explicit constructor.

      Args:
         name: A string giving the name of self.
         value: The array to serve as the memory base.
         tainted: An optional array giving the tainted flag. Default is [True].
         func: An optional argument that can be specified either by a function 
            name, or for synchronized values a dictionary of the form 
            {"name": function name}; where "name" is one of the other
            synched objects and function name is the name of a function to
            get the object "name" from self.
         synchro: An optional synchronizer object.
         dependants: An optional list containing objects that depend on self.
         dependencies: An optional list containing objects that self 
            depends upon.
         storage: An optional array giving the base array if the array is a
            slice.
      """

      super(depend_array,self).__init__(name, synchro, func, dependants, dependencies, tainted)
      if storage is None:
         self._storage=value
      else:
         self._storage=storage
            
   def __array_finalize__(self, obj):  
      """Deals with properly creating some arrays.

      In the case where a function acting on a depend array returns a ndarray, 
      this casts it into the correct form and gives it the 
      depend machinery for other methods to be able to act upon it. New
      depend_arrays will next be passed to __init__ ()to be properly 
      initialized, but some ways of creating arrays do not call __new__() or
      __init__(), so need to be initialized.
      """

      depend_base.__init__(self, name="") 
      self._storage=self
   
   # whenever possible in compound operations just return a regular ndarray
   __array_priority__=-1.0  
      
   def reshape(self, newshape):
      """Changes the shape of the base array.

      Args:
         newshape: A tuple giving the desired shape of the new array.

      Returns:
         A depend_array with the dimensions given by newshape.
      """

      return depend_array(self.base.reshape(newshape), name=self._name, synchro=self._synchro, func=self._func, dependants=self._dependants, tainted=self._tainted, storage=self._storage)  

   def flatten(self):
      """Makes the base array one dimensional."""

      return self.reshape(self.size)
   
   @staticmethod
   def __scalarindex(index, depth=1):
      """Checks if an index points at a scalar value.

      Used so that looking up one item in an array returns a scalar, whereas
      looking up a slice of the array returns a new array with the same
      dependencies as the original, so that changing the slice also changes
      the global array.

      Arguments:
         index: the index to be checked.
         depth: the rank of the array which is being accessed. Default value
            is 1. 
      
      Returns:
         A logical stating whether a __get__ instruction based
         on index would return a scalar.      
      """
      
      if (np.isscalar(index) and depth <= 1):
         return True
      elif (isinstance(index, tuple) and len(index)==depth):
         for i in index:
            if not np.isscalar(i): return False
         return True
      return False
      
   def __getitem__(self,index):
      """Returns value[index], after recalculating if necessary.

      Overwrites the standard method of getting value, so that value
      is recalculated if tainted. Scalar slices are returned as an ndarray, 
      so without depend machinery.

      Args:
         index: A slice variable giving the appropriate slice to be read.
      """

      if self.tainted():  
         self.update_auto()
         self.taint(taintme=False)
           
      if (self.__scalarindex(index, self.ndim)):
         return depstrip(self)[index]
      else:      
         return depend_array(self.base[index], name=self._name, synchro=self._synchro, func=self._func, dependants=self._dependants, tainted=self._tainted, storage=self._storage)

   def __getslice__(self,i,j):
      """Overwrites standard get function."""

      return self.__getitem__(slice(i,j,None))

   def get(self):
      """Alternative to standard get function."""

      return self.__getitem__(slice(None,None,None))
            
   def __get__(self, instance, owner):
      """Overwrites standard get function."""

      return self.__getitem__(slice(None,None,None))

   def __setitem__(self,index,value,manual=True):      
      """Alters value[index] and taints dependencies.

      Overwrites the standard method of setting value, so that dependent 
      quantities are tainted, and so we check that computed quantities are not
      manually updated.

      Args:
         index: A slice variable giving the appropriate slice to be read.
         value: The new value of the slice.
         manual: Optional boolean giving whether the value has been changed
            manually. True by default.
      """

      self.taint(taintme=False)
      if manual:
         self.base[index]=value
         self.update_man()
      else:
         self._storage[index]=value
      
   def __setslice__(self,i,j,value):
      """Overwrites standard set function."""

      return self.__setitem__(slice(i,j),value)

   def set(self, value, manual=True):
      """Alterative to standard set function.

      Args:
         See __setitem__().
      """

      self.__setitem__(slice(None,None),value=value,manual=manual)    

   def __set__(self, instance, value): 
      """Overwrites standard set function."""

      self.__setitem__(slice(None,None),value=value)

def dget(obj,member):
   """Takes an object and retrieves one of its attributes.

   Note that this is necessary as calling it in the standard way calls the
   __get__() function of member.

   Args:
      obj: A user defined class.
      member: A string giving the name of an attribute of obj.

   Exceptions:
      KeyError: If member is not an attribute of obj.

   Returns:
      obj.member.
   """

   return obj.__dict__[member]
   
def dset(obj,member,value,name=None):
   """Takes an object and sets one of its attributes.

   Necessary for editing any depend object, and should be used for
   initialising them as well, as often initialization occurs more than once, 
   with the second time effectively being an edit.

   Args:
      obj: A user defined class.
      member: A string giving the name of an attribute of obj.
      value: The new value of member.
      name: New name of member.

   Exceptions:
      KeyError: If member is not an attribute of obj.
   """

   obj.__dict__[member]=value
   if not name is None: 
      obj.__dict__[member]._name=name
   
def depstrip(deparray):
   """Removes dependencies from a depend_array.

   Takes a depend_array and returns its value as a ndarray, effectively
   stripping the dependencies from the ndarray. This speeds up a lot of
   calculations involving these arrays. Must only be used if the value of the
   array is not going to be changed.

   Args:
      deparray: A depend_array.
   
   Returns:
      A ndarray with the same value as deparray.
   """

   return deparray.view(np.ndarray)

def deppipe(objfrom,memberfrom,objto,memberto):
   """Synchronizes two depend objects.

   Takes two depend objects, and makes one of them depend on the other in such
   a way that both keep the same value. Used for attributes such as temperature
   that are used in many different modules, and so need different depend objects
   in each, but which should all have the same value.

   Args:
      objfrom: An object containing memberfrom.
      memberfrom: The base depend object.
      objto: An object containing memberto.
      memberto: The depend object that should be equal to memberfrom.
   """

   dfrom = dget(objfrom,memberfrom)
   dto = dget(objto,memberto) 
   dto._func = lambda : dfrom.get()
   dto.add_dependency(dfrom)
   
def depcopy(objfrom,memberfrom,objto,memberto):
   """Copies the dependencies of one depend object to another.

   Args:
      See deppipe.
   """
   dfrom=dget(objfrom,memberfrom)
   dto=dget(objto,memberto)
   dto._dependants=dfrom._dependants
   dto._synchro=dfrom._synchro   
   dto._tainted=dfrom._tainted
   dto._func=dfrom._func
   if hasattr(dfrom,"_storage"):
      dto._storage=dfrom._storage
   

class dobject(object): 
   """Class that allows standard notation to be used for depend objects."""
 
   def __getattribute__(self, name):
      """Overwrites standard __getattribute__().

      This changes the standard __getattribute__() function of any class that
      subclasses dobject such that depend objects are called with their own
      __get__() function rather than the standard one.
      """

      value = object.__getattribute__(self, name)
      if hasattr(value, '__get__'):
         value = value.__get__(self, self.__class__)
      return value

   def __setattr__(self, name, value):
      """Overwrites standard __setattribute__().

      This changes the standard __setattribute__() function of any class that
      subclasses dobject such that depend objects are called with their own
      __set__() function rather than the standard one.
      """

      try:
         obj = object.__getattribute__(self, name)
      except AttributeError:
         pass
      else:
         if hasattr(obj, '__set__'):
            return obj.__set__(self, value)
      return object.__setattr__(self, name, value)
