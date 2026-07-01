
echo "Run relax SnO2_2to1"
mpirun -np 128 pw.x -nk 8 -pd .true. -in ratio_2to1/relax/SnO2_2to1.relax.in > ratio_2to1/relax/SnO2_2to1.relax.out

echo "Run relax TiO2_pristine"
mpirun -np 128 pw.x -nk 8 -pd .true. -in TiO2/relax/TiO2_pristine.relax.in > TiO2/relax/TiO2_pristine.relax.out