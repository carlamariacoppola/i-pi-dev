import numpy, math, random
import thermostat

class Thermo_Langevin(thermostat.Thermostat):     
   
   def compute_TS(self):
#      print "Re-computing propagator"
      self.__T=math.exp(-self.__dt/self.__tau)
      self.__S=math.sqrt(self.temp*(1-self.__T**2))
   
   @property
   def temp(self):
 #     print "langevin temp getter called"
      return self.__temp

   @temp.setter
   def temp(self, new):
  #    print "langevin temp setter called"
      self.__temp=new
      self.compute_TS()
   
   @property
   def dt(self):
   #   print "langevin getter called"
      return self.__dt
     
   @dt.setter
   def dt(self,new):
    #  print "Thermo_Langevin setter called"
      self.__dt = new
      self.compute_TS()
   
   def __init__(self, temp = 1.0, dt = 1.0):
      self.__tau=1.0
      self.k_Boltz = 1.0
      self.__temp = temp
      self.dt = dt

   def step(self, atom):
      sigma = 1.0/(4*math.pi*self.__tau*self.k_Boltz*self.temp*atom.mass)
      for i in range(3):
         atom.p[i] = self.__T*atom.p[i] + self.__S*random.gauss(0.0, sigma)

   def cell_step(self, cell):
      sigma = 1.0/(4*math.pi*self.__tau*self.k_Boltz*self.temp*cell.w)
      for i in range(3):
         for j in range(i,3):
            cell.p[i,j] = self.__T*cell.p[i,j] + self.__S*random.gauss(0.0, sigma)

