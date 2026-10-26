"""Entrada CLI de compatibilidad: python evaluate_ai.py CASOS.json"""
import runpy
if __name__ == "__main__":
    runpy.run_module("tools.evaluate_ai", run_name="__main__")
