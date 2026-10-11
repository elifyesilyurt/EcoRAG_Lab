"""
dynamic_math_engine.py — Generalized Program-of-Thoughts (PoT) / Dynamic PAL Engine
-----------------------------------------------------------------------------------
Çok terimli ondalıklı aritmetik, oran, yüzde puanı ve karşılaştırmalı hesaplamaları
LLM'in zihinsel tahminine bırakmadan, izole ve güvenli bir Python çalışma zamanında
(AST tabanlı değerlendirme) hesaplayan dinamik matematik motoru.
Başarı, kodun hatasız çalışmasını gösterir; modelin kaynak veriyi doğru seçtiğini
ya da kayan noktalı aritmetiğin sınırsız kesinlikte olduğunu garanti etmez.
"""

import ast
import math
import operator
import re
import textwrap
from typing import Any, Dict, Optional

# İzin verilen güvenli matematiksel operatörler
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCTIONS = {
    "sum": sum,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "len": len,
    "float": float,
    "int": int,
}


class SafeMathEvaluator:
    """Güvenli AST tabanlı Python matematiksel ifade değerlendiricisi."""

    @classmethod
    def eval_expr(cls, expr: str, context: Optional[Dict[str, Any]] = None) -> Any:
        context = context or {}
        tree = ast.parse(expr, mode="eval")
        return cls._eval_node(tree.body, context)

    @staticmethod
    def _tuple_to_number(val: Any) -> Any:
        if isinstance(val, tuple) and all(isinstance(x, (int, float)) for x in val):
            s = "".join(f"{int(x):03d}" if idx > 0 else str(int(x)) for idx, x in enumerate(val))
            try:
                return float(s) if '.' in s else int(s)
            except ValueError:
                return val
        return val

    @classmethod
    def _eval_node(cls, node: ast.AST, context: Dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            if node.id in context:
                return context[node.id]
            elif node.id in _SAFE_FUNCTIONS:
                return _SAFE_FUNCTIONS[node.id]
            raise ValueError(f"Tanımsız değişken veya fonksiyon: '{node.id}'")
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _ALLOWED_OPERATORS:
                raise ValueError(f"İzin verilmeyen operatör: {op_type}")
            left = cls._tuple_to_number(cls._eval_node(node.left, context))
            right = cls._tuple_to_number(cls._eval_node(node.right, context))
            return _ALLOWED_OPERATORS[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _ALLOWED_OPERATORS:
                raise ValueError(f"İzin verilmeyen unar operatör: {op_type}")
            operand = cls._tuple_to_number(cls._eval_node(node.operand, context))
            return _ALLOWED_OPERATORS[op_type](operand)
        elif isinstance(node, ast.List):
            return [cls._tuple_to_number(cls._eval_node(elem, context)) for elem in node.elts]
        elif isinstance(node, ast.Tuple):
            raw_tup = tuple(cls._eval_node(elem, context) for elem in node.elts)
            return cls._tuple_to_number(raw_tup)
        elif isinstance(node, ast.Call):
            if node.keywords:
                raise ValueError("Keyword arguments are unsupported; use positional arguments")
            func = cls._eval_node(node.func, context)
            if func not in _SAFE_FUNCTIONS.values():
                raise ValueError(f"Güvenli olmayan fonksiyon çağrısı: {node.func}")
            args = [cls._eval_node(arg, context) for arg in node.args]
            return func(*args)
        else:
            raise ValueError(f"Desteklenmeyen sözdizimi: {type(node)}")


class DynamicMathExecutor:
    """
    Modelden gelen Program-of-Thoughts kod satırlarını veya
    sayısal formülleri çalıştıran güvenli motor.
    """

    @staticmethod
    def _validate_numeric_value(value: Any) -> None:
        """Permit finite numbers and numeric input lists; never booleans/callables."""
        if type(value) is int:
            return
        if type(value) is float and math.isfinite(value):
            return
        if isinstance(value, list):
            for item in value:
                DynamicMathExecutor._validate_numeric_value(item)
            return
        raise ValueError("Expected finite numeric data (booleans, strings and functions are not numbers)")

    @staticmethod
    def execute_code_lines(code_str: str) -> Dict[str, Any]:
        """Evaluate an entire restricted arithmetic program; fail on any error.

        Only single-name assignments and arithmetic expressions are supported.
        The final statement must produce a finite numeric scalar. Failed runs
        expose no usable environment/result; trace and errors are diagnostic only.
        Syntax is parsed before evaluation, so invalid statements are never skipped.
        """
        env: Dict[str, Any] = {}
        execution_trace = []
        errors = []
        final_value = None
        final_name = None

        def failure(line: int, kind: str, message: str) -> Dict[str, Any]:
            errors.append({"line": line, "type": kind, "message": message})
            execution_trace.append(f"Line {line}: HATA ({message})")
            return {"environment": {}, "trace": execution_trace, "success": False,
                    "result": None, "result_name": None, "errors": errors}

        if not isinstance(code_str, str):
            return failure(1, "InvalidInput", "Expected Python code as text")
        clean_code = textwrap.dedent(code_str).strip()
        fence = re.fullmatch(r"```(?:python)?\s*\n(.*?)\n```", clean_code, flags=re.DOTALL)
        if fence:
            clean_code = textwrap.dedent(fence.group(1)).strip()
        try:
            program = ast.parse(clean_code, mode="exec")
        except SyntaxError as exc:
            return failure(exc.lineno or 1, "SyntaxError", exc.msg)
        if not program.body:
            return failure(1, "EmptyProgram", "No arithmetic statements were provided")

        for statement in program.body:
            try:
                if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                        and isinstance(statement.targets[0], ast.Name)):
                    name = statement.targets[0].id
                    expression = statement.value
                elif isinstance(statement, ast.Expr):
                    name = "_result"
                    expression = statement.value
                else:
                    raise ValueError("Only single-name assignments and arithmetic expressions are supported")
                value = SafeMathEvaluator._eval_node(expression, env)
                DynamicMathExecutor._validate_numeric_value(value)
                env[name] = value
                execution_trace.append(f"{name} = {value}")
                final_value, final_name = value, name
            except Exception as exc:
                return failure(statement.lineno, type(exc).__name__, str(exc))

        if type(final_value) not in (int, float):
            return failure(program.body[-1].lineno, "MissingNumericResult",
                           "The final statement must produce a finite numeric scalar")
        return {"environment": env, "trace": execution_trace, "success": True,
                "result": final_value, "result_name": final_name, "errors": errors}


def format_math_execution_result(result: Dict[str, Any]) -> Optional[str]:
    """Return synthesis input only for complete successful arithmetic programs."""
    value = result.get("result")
    if (not result.get("success") or result.get("errors")
            or type(value) not in (int, float)
            or (type(value) is float and not math.isfinite(value))):
        return None
    name = result.get("result_name") or "_result"
    lines = [f"Final result ({name}): {value!r}"]
    for variable, intermediate in result.get("environment", {}).items():
        if variable != name and not variable.startswith("_"):
            lines.append(f"{variable}: {intermediate!r}")
    return "\n".join(lines)


def math_execution_failure_message(lang: str = "tr") -> str:
    """Fail closed: do not ask the model to guess after arithmetic failure."""
    if lang == "tr":
        return ("Hesaplama tamamlanamadı; doğrulanmış bir sayısal sonuç sunamıyorum. "
                "Lütfen sorudaki yılı, birimi ve hesaplanacak değerleri netleştirin.")
    return ("The calculation could not be completed; I cannot provide a verified numeric result. "
            "Please clarify the year, units, and values to calculate.")


# Program-of-Thoughts Sistem İstemi
POT_EXTRACTION_SYSTEM_PROMPT = """You are a Program-Aided Language (PAL) Data Extraction & Math Engine.
Your task is to extract exact numbers from the provided report context and output EXECUTABLE PYTHON CODE to answer the question mathematically.

STRICT PROTOCOL:
1. Extract exact numbers directly from the report text or tables. Do not alter any numbers.
2. DO NOT calculate any results in your head. Write Python variable assignments and arithmetic formulas instead.
3. When summing multiple listed items/categories, explicitly put all extracted values into a Python list and use sum():
   e.g.: others = [3.39, 1.99, 0.05, 0.81, 1.22, 0.45, 14.05, 0.03, 0.05]
         others_total = sum(others)
4. Allowed operations & functions: +, -, *, /, sum(), min(), max(), abs(), round(), len().
5. End with a finite numeric scalar answer, e.g. result = group1_total - group2_total.
6. Use only single-name assignments and arithmetic expressions; no imports, prose, comparisons, or keyword arguments.
7. Use positional arguments for functions, e.g. round(value, 2). Do not output booleans, strings, NaN, or infinity.

Example format:
```python
# Extracted numbers from report
cat1 = 36.23
cat2 = 38.24
top2_total = cat1 + cat2

# Sum of other listed categories
others = [3.39, 1.99, 0.05, 0.81, 1.22, 0.45, 14.05, 0.03, 0.05]
others_total = sum(others)

# Difference in percentage points
difference_points = top2_total - others_total
```
Respond ONLY with the Python code block."""


def is_mathematical_query(query: str) -> bool:
    """Sorgunun matematiksel hesaplama, karşılaştırma veya toplama gerektirip gerektirmediğini tespit eder."""
    q = query.lower()
    math_signals = [
        r"\btoplam\b", r"\btoplamı\b", r"\btoplam kaç\b", r"\bfark\b", r"\bfarkı\b", r"\bkaç puan\b", r"\byüzde puan\b",
        r"\bartış\b", r"\bazalış\b", r"\boran\b", r"\boranı\b", r"\byüzdesi\b", r"\byüzde kaç\b", r"\bkatı\b", r"\bdeğişim\b",
        r"\bhesapla\b", r"\bkarşılaştır\b", r"\bsum\b", r"\btotal\b", r"\bdifference\b", r"\bdelta\b", r"\bratio\b",
        r"\bpercentage point\b", r"\bpercentage points\b", r"\bincrease\b", r"\bdecrease\b", r"\bcompare\b",
        r"\bhigher\b", r"\blower\b", r"\bhow much more\b", r"\bhow much less\b"
    ]
    return any(bool(re.search(pat, q)) for pat in math_signals)


