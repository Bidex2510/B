"""Calculator plugin - safe math evaluation."""

import re
import math
import operator

from jarvis.core.plugin_base import PluginBase

SAFE_OPERATORS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "**": operator.pow,
    "%": operator.mod,
}

SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "pi": math.pi,
    "e": math.e,
}


class CalculatorPlugin(PluginBase):

    name = "calculator"
    description = "Perform mathematical calculations (basic and scientific)"

    TRIGGERS = [
        r"\b(calculate|calc|math|compute|what is|what's)\b.*\d",
        r"\d+\s*[\+\-\*\/\%\^]\s*\d+",
        r"\b(sqrt|sin|cos|tan|log)\b",
    ]

    def can_handle(self, text):
        return any(re.search(t, text, re.IGNORECASE) for t in self.TRIGGERS)

    def handle(self, text):
        # Extract the math expression
        expr = re.sub(
            r"\b(calculate|calc|compute|what is|what's|please|jarvis|the result of)\b",
            "", text, flags=re.IGNORECASE,
        ).strip().strip("?.,!")

        expr = expr.replace("^", "**").replace("x", "*")

        try:
            result = self._safe_eval(expr)
            if isinstance(result, float) and result == int(result):
                result = int(result)
            return f"The result is: {result}"
        except ZeroDivisionError:
            return "Division by zero is undefined, sir."
        except Exception:
            return f"I couldn't compute that expression, sir. Please rephrase it."

    def _safe_eval(self, expr):
        allowed_chars = set("0123456789.+-*/%() ,")
        # Allow function names
        cleaned = expr
        for fn in SAFE_FUNCTIONS:
            cleaned = cleaned.replace(fn, "")

        if not all(c in allowed_chars for c in cleaned.replace(" ", "")):
            raise ValueError("Unsafe expression")

        return eval(expr, {"__builtins__": {}}, SAFE_FUNCTIONS)
