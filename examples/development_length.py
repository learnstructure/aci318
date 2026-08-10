"""
Development length and splice example.
"""

from aci318 import ACI318_19, Concrete, Steel
from aci318.database import BAR_DATABASE
from aci318 import calculate_development_length

concrete = Concrete(fc=4.0)
steel = Steel(fy=60.0)
code = ACI318_19()
bar_sizes = ["#4", "#6", "#8", "#10"]

for bar in bar_sizes:
    db = BAR_DATABASE[bar]["diameter"]
    result = calculate_development_length(
        bar_diameter=db,
        steel=steel,
        concrete=concrete,
        code=code,
        is_top_bar=False,
        is_epoxy=False,
        is_lightweight=False,
    )
    print(f"{bar}: ld_t = {result.ld_tension:.1f} in, ld_c = {result.ld_compression:.1f} in")
