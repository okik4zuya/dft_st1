root@8379e2f197af:/quickpod/QE# grep -i "error\|Error\|stopping\|STOP\|not found\|pseudo" \
    pristine/relax/SnO2_pristine.relax.out | tail -30
     Error in routine  system_checkin (1):
     stopping ...
with errorcode 1.
[8379e2f197af:22904] Set MCA parameter "orte_base_help_aggregate" to 0 to see all help / error messages
root@8379e2f197af:/quickpod/QE# grep -i "hubbard\|lda_plus_u\|unrecognized\|not allowed\|namelist" \
    pristine/relax/SnO2_pristine.relax.out | head -20
     WARNING!!! The input parameter lda_plus_u is obsolete.
     WARNING!!! The input parameter lda_plus_u_kind is obsolete.
     WARNING!!! The input parameter Hubbard_U is obsolete.
     WARNING!!! The input syntax for DFT+Hubbard codes has changed since v7.1
     WARNING!!! Check the new documentation (Doc/Hubbard_input)!
     DFT+Hubbard input syntax has changed since v7.1
root@8379e2f197af:/quickpod/QE# grep -B5 "system_checkin" \
    pristine/relax/SnO2_pristine.relax.out
     WARNING!!! The input syntax for DFT+Hubbard codes has changed since v7.1

     WARNING!!! Check the new documentation (Doc/Hubbard_input)!

 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
     Error in routine  system_checkin (1):
root@8379e2f197af:/quickpod/QE# grep -i "lda_plus_u\|hubbard\|Hubbard" \
    pristine/relax/SnO2_pristine.relax.in
  lda_plus_u       = .true.
  lda_plus_u_kind  = 0         ! Dudarev simplified (Ueff = U - J)
  Hubbard_U(1)     = 4.0       ! Sn 4d (eV)
  Hubbard_U(2)     = 0.0       ! O 2p
root@8379e2f197af:/quickpod/QE#

