===== NSCF OUT TAIL =====
       0.999  0.999  1.000  1.000  1.000
     eigenvectors (columns):
       0.607 -0.000 -0.794 -0.000  0.000
      -0.000 -0.707  0.000  0.707  0.000
      -0.000 -0.707  0.000 -0.707 -0.000
       0.000  0.000  0.000 -0.000  1.000
       0.794 -0.000  0.607 -0.000 -0.000
     occupation matrix ns (before diag.):
       0.999 -0.000 -0.000 -0.000 -0.000
      -0.000  0.999 -0.000  0.000  0.000
      -0.000 -0.000  0.999  0.000  0.000
      -0.000  0.000  0.000  1.000 -0.000
      -0.000  0.000  0.000 -0.000  0.999

     Number of occupied Hubbard levels =   79.9610

     Atomic wfc used for Hubbard projectors are orthogonalized

     Starting wfcs are  136 randomized atomic wfcs +   24 random wfcs
     Checking if some PAW data can be deallocated...

     Band Structure Calculation
     Davidson diagonalization with overlap

 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
     Error in routine  cdiaghg (227):
      problems computing cholesky
 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

     stopping ...
--------------------------------------------------------------------------
MPI_ABORT was invoked on rank 0 in communicator MPI_COMM_WORLD
with errorcode 227.

NOTE: invoking MPI_ABORT causes Open MPI to kill all MPI processes.
You may or may not see output from other processes, depending on
exactly when Open MPI kills them.
--------------------------------------------------------------------------
[acefeb18ed8f:23614] 3 more processes have sent help message help-mpi-api.txt / mpi-abort
[acefeb18ed8f:23614] Set MCA parameter "orte_base_help_aggregate" to 0 to see all help / error messages

===== ERROR LINES =====
34:     Found identity + ( -0.5000  0.0000  0.0000) symmetry
37:     using ibrav=0 with symmetry is DISCOURAGED, use correct ibrav instead
38:     [opt_tetra]  Optimized tetrahedron method is used.
155:     number of k points=   147 (tetrahedron method)
159:     Dense  grid:   349947 G-vectors     FFT dimensions: ( 125, 125,  45)
161:     Smooth grid:   123705 G-vectors     FFT dimensions: (  90,  90,  30)
313: %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
314:     Error in routine  cdiaghg (227):
316: %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
318:     stopping ...
321:with errorcode 227.
328:[acefeb18ed8f:23614] Set MCA parameter "orte_base_help_aggregate" to 0 to see all help / error messages

root@acefeb18ed8f:/quickpod/QE/pristine/nscf# echo "===== TMP LINK ====="; ls -ld tmp; ls -l ../scf/tmp/ 2>/dev/null
echo "===== SCF SAVE ====="; ls -l ../scf/tmp/SnO2_pristine.save/ 2>/dev/null | head
echo "===== XML PRESENT? ====="; ls -l ../scf/tmp/SnO2_pristine.save/data-file-schema.xml 2>/dev/null
===== TMP LINK =====
lrwxrwxrwx 1 root root 10 Jun 27 15:03 tmp -> ../scf/tmp
total 2567800
-rw-r--r-- 1 root root 23870080 Jun 27 15:03 SnO2_pristine.hub1
-rw-r--r-- 1 root root 23870080 Jun 27 15:03 SnO2_pristine.hub10
-rw-r--r-- 1 root root 23833600 Jun 27 15:03 SnO2_pristine.hub11
-rw-r--r-- 1 root root 23687680 Jun 27 15:03 SnO2_pristine.hub12
-rw-r--r-- 1 root root 23712000 Jun 27 15:03 SnO2_pristine.hub13
-rw-r--r-- 1 root root 23639040 Jun 27 15:03 SnO2_pristine.hub14
-rw-r--r-- 1 root root 23566080 Jun 27 15:03 SnO2_pristine.hub15
-rw-r--r-- 1 root root 23748480 Jun 27 15:03 SnO2_pristine.hub16
-rw-r--r-- 1 root root 23870080 Jun 27 15:03 SnO2_pristine.hub17
-rw-r--r-- 1 root root 23870080 Jun 27 15:03 SnO2_pristine.hub18
-rw-r--r-- 1 root root 23833600 Jun 27 15:03 SnO2_pristine.hub19
-rw-r--r-- 1 root root 23870080 Jun 27 15:03 SnO2_pristine.hub2
-rw-r--r-- 1 root root 23687680 Jun 27 15:03 SnO2_pristine.hub20
-rw-r--r-- 1 root root 23712000 Jun 27 15:03 SnO2_pristine.hub21
-rw-r--r-- 1 root root 23639040 Jun 27 15:03 SnO2_pristine.hub22
-rw-r--r-- 1 root root 23566080 Jun 27 15:03 SnO2_pristine.hub23
-rw-r--r-- 1 root root 23748480 Jun 27 15:03 SnO2_pristine.hub24
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub25
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub26
-rw-r--r-- 1 root root 22579200 Jun 27 15:03 SnO2_pristine.hub27
-rw-r--r-- 1 root root 22440960 Jun 27 15:03 SnO2_pristine.hub28
-rw-r--r-- 1 root root 22464000 Jun 27 15:03 SnO2_pristine.hub29
-rw-r--r-- 1 root root 23833600 Jun 27 15:03 SnO2_pristine.hub3
-rw-r--r-- 1 root root 22394880 Jun 27 15:03 SnO2_pristine.hub30
-rw-r--r-- 1 root root 22325760 Jun 27 15:03 SnO2_pristine.hub31
-rw-r--r-- 1 root root 22498560 Jun 27 15:03 SnO2_pristine.hub32
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub33
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub34
-rw-r--r-- 1 root root 22579200 Jun 27 15:03 SnO2_pristine.hub35
-rw-r--r-- 1 root root 22440960 Jun 27 15:03 SnO2_pristine.hub36
-rw-r--r-- 1 root root 22464000 Jun 27 15:03 SnO2_pristine.hub37
-rw-r--r-- 1 root root 22394880 Jun 27 15:03 SnO2_pristine.hub38
-rw-r--r-- 1 root root 22325760 Jun 27 15:03 SnO2_pristine.hub39
-rw-r--r-- 1 root root 23687680 Jun 27 15:03 SnO2_pristine.hub4
-rw-r--r-- 1 root root 22498560 Jun 27 15:03 SnO2_pristine.hub40
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub41
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub42
-rw-r--r-- 1 root root 22579200 Jun 27 15:03 SnO2_pristine.hub43
-rw-r--r-- 1 root root 22440960 Jun 27 15:03 SnO2_pristine.hub44
-rw-r--r-- 1 root root 22464000 Jun 27 15:03 SnO2_pristine.hub45
-rw-r--r-- 1 root root 22394880 Jun 27 15:03 SnO2_pristine.hub46
-rw-r--r-- 1 root root 22325760 Jun 27 15:03 SnO2_pristine.hub47
-rw-r--r-- 1 root root 22498560 Jun 27 15:03 SnO2_pristine.hub48
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub49
-rw-r--r-- 1 root root 23712000 Jun 27 15:03 SnO2_pristine.hub5
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub50
-rw-r--r-- 1 root root 22579200 Jun 27 15:03 SnO2_pristine.hub51
-rw-r--r-- 1 root root 22440960 Jun 27 15:03 SnO2_pristine.hub52
-rw-r--r-- 1 root root 22464000 Jun 27 15:03 SnO2_pristine.hub53
-rw-r--r-- 1 root root 22394880 Jun 27 15:03 SnO2_pristine.hub54
-rw-r--r-- 1 root root 22325760 Jun 27 15:03 SnO2_pristine.hub55
-rw-r--r-- 1 root root 22498560 Jun 27 15:03 SnO2_pristine.hub56
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub57
-rw-r--r-- 1 root root 22613760 Jun 27 15:03 SnO2_pristine.hub58
-rw-r--r-- 1 root root 22579200 Jun 27 15:03 SnO2_pristine.hub59
-rw-r--r-- 1 root root 23639040 Jun 27 15:03 SnO2_pristine.hub6
-rw-r--r-- 1 root root 22440960 Jun 27 15:03 SnO2_pristine.hub60
-rw-r--r-- 1 root root 22464000 Jun 27 15:03 SnO2_pristine.hub61
-rw-r--r-- 1 root root 22394880 Jun 27 15:03 SnO2_pristine.hub62
-rw-r--r-- 1 root root 22325760 Jun 27 15:03 SnO2_pristine.hub63
-rw-r--r-- 1 root root 22498560 Jun 27 15:03 SnO2_pristine.hub64
-rw-r--r-- 1 root root 23566080 Jun 27 15:03 SnO2_pristine.hub7
-rw-r--r-- 1 root root 23748480 Jun 27 15:03 SnO2_pristine.hub8
-rw-r--r-- 1 root root 23870080 Jun 27 15:03 SnO2_pristine.hub9
drwxr-xr-x 2 root root     4096 Jun 27 14:19 SnO2_pristine.save
-rw-r--r-- 1 root root 15075840 Jun 27 15:07 SnO2_pristine.wfc1
-rw-r--r-- 1 root root 15075840 Jun 27 15:07 SnO2_pristine.wfc10
-rw-r--r-- 1 root root 15052800 Jun 27 15:07 SnO2_pristine.wfc11
-rw-r--r-- 1 root root 14960640 Jun 27 15:07 SnO2_pristine.wfc12
-rw-r--r-- 1 root root 14976000 Jun 27 15:07 SnO2_pristine.wfc13
-rw-r--r-- 1 root root 14929920 Jun 27 15:07 SnO2_pristine.wfc14
-rw-r--r-- 1 root root 14883840 Jun 27 15:07 SnO2_pristine.wfc15
-rw-r--r-- 1 root root 14999040 Jun 27 15:07 SnO2_pristine.wfc16
-rw-r--r-- 1 root root 20101120 Jun 27 15:08 SnO2_pristine.wfc17
-rw-r--r-- 1 root root 20101120 Jun 27 15:08 SnO2_pristine.wfc18
-rw-r--r-- 1 root root 20070400 Jun 27 15:08 SnO2_pristine.wfc19
-rw-r--r-- 1 root root 15075840 Jun 27 15:07 SnO2_pristine.wfc2
-rw-r--r-- 1 root root 19947520 Jun 27 15:08 SnO2_pristine.wfc20
-rw-r--r-- 1 root root 19968000 Jun 27 15:08 SnO2_pristine.wfc21
-rw-r--r-- 1 root root 19906560 Jun 27 15:08 SnO2_pristine.wfc22
-rw-r--r-- 1 root root 19845120 Jun 27 15:08 SnO2_pristine.wfc23
-rw-r--r-- 1 root root 19998720 Jun 27 15:08 SnO2_pristine.wfc24
-rw-r--r-- 1 root root 20101120 Jun 27 15:08 SnO2_pristine.wfc25
-rw-r--r-- 1 root root 20101120 Jun 27 15:08 SnO2_pristine.wfc26
-rw-r--r-- 1 root root 20070400 Jun 27 15:08 SnO2_pristine.wfc27
-rw-r--r-- 1 root root 19947520 Jun 27 15:08 SnO2_pristine.wfc28
-rw-r--r-- 1 root root 19968000 Jun 27 15:08 SnO2_pristine.wfc29
-rw-r--r-- 1 root root 15052800 Jun 27 15:07 SnO2_pristine.wfc3
-rw-r--r-- 1 root root 19906560 Jun 27 15:08 SnO2_pristine.wfc30
-rw-r--r-- 1 root root 19845120 Jun 27 15:08 SnO2_pristine.wfc31
-rw-r--r-- 1 root root 19998720 Jun 27 15:08 SnO2_pristine.wfc32
-rw-r--r-- 1 root root 15075840 Jun 27 15:07 SnO2_pristine.wfc33
-rw-r--r-- 1 root root 15075840 Jun 27 15:07 SnO2_pristine.wfc34
-rw-r--r-- 1 root root 15052800 Jun 27 15:07 SnO2_pristine.wfc35
-rw-r--r-- 1 root root 14960640 Jun 27 15:07 SnO2_pristine.wfc36
-rw-r--r-- 1 root root 14976000 Jun 27 15:07 SnO2_pristine.wfc37
-rw-r--r-- 1 root root 14929920 Jun 27 15:07 SnO2_pristine.wfc38
-rw-r--r-- 1 root root 14883840 Jun 27 15:07 SnO2_pristine.wfc39
-rw-r--r-- 1 root root 14960640 Jun 27 15:07 SnO2_pristine.wfc4
-rw-r--r-- 1 root root 14999040 Jun 27 15:07 SnO2_pristine.wfc40
-rw-r--r-- 1 root root 20101120 Jun 27 15:08 SnO2_pristine.wfc41
-rw-r--r-- 1 root root 20101120 Jun 27 15:08 SnO2_pristine.wfc42
-rw-r--r-- 1 root root 20070400 Jun 27 15:08 SnO2_pristine.wfc43
-rw-r--r-- 1 root root 19947520 Jun 27 15:08 SnO2_pristine.wfc44
-rw-r--r-- 1 root root 19968000 Jun 27 15:08 SnO2_pristine.wfc45
-rw-r--r-- 1 root root 19906560 Jun 27 15:08 SnO2_pristine.wfc46
-rw-r--r-- 1 root root 19845120 Jun 27 15:08 SnO2_pristine.wfc47
-rw-r--r-- 1 root root 19998720 Jun 27 15:08 SnO2_pristine.wfc48
-rw-r--r-- 1 root root 20101120 Jun 27 15:09 SnO2_pristine.wfc49
-rw-r--r-- 1 root root 14976000 Jun 27 15:07 SnO2_pristine.wfc5
-rw-r--r-- 1 root root 20101120 Jun 27 15:09 SnO2_pristine.wfc50
-rw-r--r-- 1 root root 20070400 Jun 27 15:09 SnO2_pristine.wfc51
-rw-r--r-- 1 root root 19947520 Jun 27 15:09 SnO2_pristine.wfc52
-rw-r--r-- 1 root root 19968000 Jun 27 15:09 SnO2_pristine.wfc53
-rw-r--r-- 1 root root 19906560 Jun 27 15:09 SnO2_pristine.wfc54
-rw-r--r-- 1 root root 19845120 Jun 27 15:09 SnO2_pristine.wfc55
-rw-r--r-- 1 root root 19998720 Jun 27 15:09 SnO2_pristine.wfc56
-rw-r--r-- 1 root root 20101120 Jun 27 15:08 SnO2_pristine.wfc57
-rw-r--r-- 1 root root 20101120 Jun 27 15:08 SnO2_pristine.wfc58
-rw-r--r-- 1 root root 20070400 Jun 27 15:08 SnO2_pristine.wfc59
-rw-r--r-- 1 root root 14929920 Jun 27 15:07 SnO2_pristine.wfc6
-rw-r--r-- 1 root root 19947520 Jun 27 15:08 SnO2_pristine.wfc60
-rw-r--r-- 1 root root 19968000 Jun 27 15:08 SnO2_pristine.wfc61
-rw-r--r-- 1 root root 19906560 Jun 27 15:08 SnO2_pristine.wfc62
-rw-r--r-- 1 root root 19845120 Jun 27 15:08 SnO2_pristine.wfc63
-rw-r--r-- 1 root root 19998720 Jun 27 15:08 SnO2_pristine.wfc64
-rw-r--r-- 1 root root 14883840 Jun 27 15:07 SnO2_pristine.wfc7
-rw-r--r-- 1 root root 14999040 Jun 27 15:07 SnO2_pristine.wfc8
-rw-r--r-- 1 root root 15075840 Jun 27 15:07 SnO2_pristine.wfc9
-rw-r--r-- 1 root root   267832 Jun 27 14:19 SnO2_pristine.xml
===== SCF SAVE =====
total 1076196
-rw-r--r-- 1 root root   875308 Jun 27 14:19 O.pbesol-n-kjpaw_psl.1.0.0.UPF
-rw-r--r-- 1 root root  2017097 Jun 27 14:19 Sn.pbesol-dn-kjpaw_psl.1.0.0.UPF
-rw-r--r-- 1 root root  9798632 Jun 27 14:19 charge-density.dat
-rw-r--r-- 1 root root   267832 Jun 27 14:19 data-file-schema.xml
-rw-r--r-- 1 root root    15601 Jun 27 14:19 occup.txt
-rw-r--r-- 1 root root   106705 Jun 27 14:19 paw.txt
-rw-r--r-- 1 root root 31152960 Jun 27 14:19 wfc1.dat
-rw-r--r-- 1 root root 30957796 Jun 27 14:19 wfc10.dat
-rw-r--r-- 1 root root 31146924 Jun 27 14:19 wfc11.dat
===== XML PRESENT? =====
-rw-r--r-- 1 root root 267832 Jun 27 14:19 ../scf/tmp/SnO2_pristine.save/data-file-schema.xml
root@acefeb18ed8f:/quickpod/QE/pristine/nscf# echo "===== SCF JOB DONE? ====="; grep -c "JOB DONE" ../scf/SnO2_pristine.scf.out; tail -5 ../scf/SnO2_pristine.scf.out
===== SCF JOB DONE? =====
1
   This run was terminated on:  14:19:59  27Jun2026

=------------------------------------------------------------------------------=
   JOB DONE.
=------------------------------------------------------------------------------=

