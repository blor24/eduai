"""Se ejecuta sin Django/Flask/Ollama: python3 -m unittest discover -s tests"""
import ast
from pathlib import Path
import importlib.util
import unittest

KIT = Path(__file__).resolve().parents[1]
MODULE = KIT / 'archivos/backend/eduai_difficulty.py'
spec = importlib.util.spec_from_file_location('eduai_difficulty', MODULE)
dif = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dif)


class DifficultyTest(unittest.TestCase):
    def test_legal_levels(self):
        self.assertEqual(set(dif.NIVELES), {'basica', 'intermedia', 'avanzada', 'mixta'})
        for value in dif.NIVELES:
            self.assertGreater(len(dif.instrucciones(value)), 20)

    def test_invalid_level(self):
        with self.assertRaises(ValueError):
            dif.instrucciones('muy-dificil')
        with self.assertRaises(ValueError):
            dif.plan_generacion('multiple', 3, 'cualquiera')

    def test_counts_and_batches(self):
        for kind in ('multiple','corta','espacio','emparejar'):
            for level in dif.NIVELES:
                for amount in range(1,41):
                    plan = dif.plan_generacion(kind, amount, level)
                    self.assertEqual(sum(size for _,size in plan), amount)
                    self.assertTrue(all(1 <= n <= (40 if kind == 'emparejar' else 4) for _,n in plan))
                    self.assertEqual(len(plan), 1 if kind == 'emparejar' else len(plan))

    def test_mixed_balancing(self):
        for amount in range(3,41):
            plan = dif.plan_generacion('multiple', amount, 'mixta')
            counts = {lvl:sum(n for key,n in plan if key == lvl) for lvl in ('basica','intermedia','avanzada')}
            self.assertLessEqual(max(counts.values())-min(counts.values()),1)

    def test_matching_is_single_exercise(self):
        self.assertEqual(dif.plan_generacion('emparejar', 6, 'mixta'), [('mixta',6)])

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            dif.plan_generacion('true-false',2,'basica')


class ModelIntegrationTest(unittest.TestCase):
    """Ejecuta el método real usando doubles, sin librerías LLM instaladas."""
    def test_question_generator_method_integration(self):
        tested_llm = KIT.parent / 'eduai_dev_staging/backend/llmgeneration.py'
        if not tested_llm.exists():
            self.skipTest('Requiere copiar el proyecto integrado a eduai_dev_staging')
        source = tested_llm.read_text(encoding='utf-8')
        module = ast.parse(source)
        cls = next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='QuestionGenerator')
        method = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='generate_all_types')
        code = compile(ast.Module(body=[method],type_ignores=[]), '<generator>', 'exec')
        scope = {'plan_generacion': dif.plan_generacion, 'NIVELES':dif.NIVELES}
        exec(code,scope)
        class Stub:
            prompts = {'multiple':1,'emparejar':1}
            def get_documents(self, namespace, filename): return ['Documento']
            def _batch(self, kind, amount, passage, dificultad):
                if kind=='emparejar':
                    return [{'terms':[str(i) for i in range(amount)],'concepts':[str(i) for i in range(amount)]}]
                return [{'question':'ok','options':['a','b','c','d'], 'correct_answer':'a','explanation':'test'} for _ in range(amount)]
        fn=scope['generate_all_types']
        result=fn(Stub(),['multiple','emparejar'],5,'user','filename','mixta')
        self.assertEqual(len(result['multiple']['questions']), 5)
        self.assertEqual(len(result['emparejar']['questions']), 1)
        self.assertEqual([p['eduai_dificultad'] for p in result['multiple']['questions']].count('basica'),2)
        self.assertEqual(result['emparejar']['questions'][0]['eduai_dificultad'],'intermedia')


if __name__ == '__main__':
    unittest.main()
