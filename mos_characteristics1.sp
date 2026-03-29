* MOS Characteristic Curves
* LPA 8/13/2019

******************************
* Include model files
******************************
.include ./models/22nm_bulk.pm
******************************
* Additional options
******************************
.option TEMP=27C

******************************
* Circuit netlist
******************************

vd		drain gnd	dc 0.4
vg		gate gnd 	dc 0.8

mn0		drain gate gnd gnd 	nmos	W=1.76u L=22n

******************************
* Control section
******************************

.control 
dc vg 0 0.8 0.01

.endc


******************************
* End of file
******************************
.end


