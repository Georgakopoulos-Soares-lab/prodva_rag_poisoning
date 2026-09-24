"""Colorblind-safe palette (Okabe-Ito) and the project's semantic color mapping.

Keep the SAME semantic mapping across every figure: query style and attack arm always get
the same encoding so a reader can carry meaning from one panel to the next.
"""
# Okabe-Ito (colorblind-safe)
BLACK      = "#000000"
ORANGE     = "#E69F00"
SKYBLUE    = "#56B4E9"
GREEN      = "#009E73"
YELLOW     = "#F0E442"
BLUE       = "#0072B2"
VERMILLION = "#D55E00"
PURPLE     = "#CC79A7"
GREY       = "#8C8C8C"

OKABE_ITO = [BLUE, VERMILLION, GREEN, ORANGE, SKYBLUE, PURPLE, YELLOW, BLACK]

# Query phrasing (consistent everywhere)
QUERY_STYLE = {"templated": BLUE, "free_text": VERMILLION}
QUERY_STYLE_LABEL = {"templated": "Templated queries", "free_text": "Free-text queries"}

# Attack arms
ARM = {"random": GREY, "targeted": BLUE, "universal": GREEN}

# Downstream end-to-end arms (mix of attack x style): keep distinct but meaningful
E2E = {"neardup_templated": BLUE, "neardup_freetext": VERMILLION, "universal_freetext": GREEN}
