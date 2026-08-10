"""
ACI 318 code factors example.
"""

from aci318 import ACI318_19, Concrete

code = ACI318_19()

print("φ Flexure at εt = 0.003 ->", code.get_phi_flexure(strain_t=0.003))
print("β1 at f'c = 4 ksi ->", code.get_beta_1(4.0))
print("λ for normalweight concrete ->", code.get_lambda_(Concrete(fc=4.0, concrete_type="normalweight", density=145.0)))
