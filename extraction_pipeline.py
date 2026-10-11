import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ExtractedMetric(BaseModel):
    entity: str = Field(description="The subject/entity (e.g., Replenishment Projects, Water Benefit, Zero Waste Datacenters)")
    metric_type: str = Field(description="Type of metric: volume, count, emissions, percentage, energy, certification, standard")
    value: float = Field(default=0.0, description="The numeric value extracted. Set to 0.0 if the metric is non-numeric (e.g., a certification name).")
    string_value: Optional[str] = Field(default=None, description="Non-numeric value (e.g., certification name, standard name). Use when value cannot be expressed as a number.")
    unit: str = Field(description="Unit of measurement: m3, million m3, projects, metric tons, datacenters, %, name, standard")
    temporal_scope: str = Field(description="Time period: FY20, FY23, FY24, FY25, Lifetime")
    is_cumulative: bool = Field(description="True if lifetime/cumulative total, False if annual/in-year")
    raw_quote: str = Field(description="Exact sentence quote from context")

class QueryExtractionPlan(BaseModel):
    reasoning: str
    metrics: List[ExtractedMetric]
    information_found: bool

EXTRACTION_SYSTEM_PROMPT = """You are a Strict Quantitative Information Extraction Engine.
Your task is to extract all relevant numerical metrics, physical units, entities, and temporal scopes from the context matching the user query.

STRICT PROTOCOL:
1. Extract numerical values with their EXACT bound units (e.g., m3, million m3, projects, metric tons).
   Qualified disclosures (more than, nearly, approximately) are not exact scalars. Contracted future deliveries are not realized annual removals. Missing allocations are not zero. For an exact calculation without exact inputs, set information_found to false and metrics to [].
2. Differentiate strictly between counts (e.g., projects, facilities) and physical metrics (e.g., m3, metric tons).
3. Differentiate strictly between cumulative/lifetime totals and single-year additions.
4. For NON-NUMERIC facts (e.g., certification names, standard names, program names): set metric_type to "certification" or "standard", set value to 0.0, and put the text in string_value.
5. If the exact specific information requested is completely missing, set "information_found": false and "metrics": [].
6. If context contains [VISUAL REFERENCE] or [VISUAL DATA FRAGMENT] warnings, do NOT extract numbers from those chunks.

Respond ONLY with a valid JSON object adhering strictly to the JSON schema:
{
  "reasoning": "brief explanation",
  "information_found": true,
  "metrics": [
    {
      "entity": "string",
      "metric_type": "volume|count|emissions|percentage|energy|certification|standard",
      "value": 0.0,
      "string_value": null,
      "unit": "string",
      "temporal_scope": "string",
      "is_cumulative": true,
      "raw_quote": "string"
    }
  ]
}"""

def format_extraction_prompt(query: str, context_chunks: List[str]) -> str:
    joined_context = "\n---\n".join(context_chunks)
    return f"Context:\n{joined_context}\n\nUser Query: {query}\n\nOutput JSON:"

class DeterministicResolver:
    @staticmethod
    def validate_and_filter(extraction_plan: QueryExtractionPlan, query: str) -> Dict[str, Any]:
        if not extraction_plan.information_found or not extraction_plan.metrics:
            return {
                "status": "NOT_FOUND",
                "message": "The provided documents do not contain the specific data requested."
            }

        query_lower = query.lower()
        wants_volume = any(w in query_lower for w in ["volume", "consumed", "withdrawn", "hacim", "benefit"])
        wants_count  = any(w in query_lower for w in ["how many", "count", "number of", "projects count"])
        wants_cert   = any(w in query_lower for w in ["certification", "certified", "standard", "accreditation", "validate"])

        validated_results = []
        for m in extraction_plan.metrics:
            # Hacim sorusunda proje/bina adedini filtrele
            if wants_volume and not wants_count and m.metric_type == "count" and m.unit in ["projects", "buildings", "facilities"]:
                continue
            # Sertifikasyon sorgularında sayısal olmayan metriklere (metric_type=certification/standard) izin ver
            if wants_cert and m.metric_type in ["certification", "standard"]:
                validated_results.append(m)
                continue
            validated_results.append(m)

        if not validated_results:
            return {
                "status": "NOT_FOUND",
                "message": "No matching metrics found after assertion checks."
            }

        return {
            "status": "SUCCESS",
            "metrics": validated_results
        }
