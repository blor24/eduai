import sys
from pathlib import Path
import unittest

APP = Path(__file__).resolve().parents[1] / 'archivos/frontend/djtesis/tesis'
sys.path.insert(0, str(APP))
from banco_logic import normalizar_pregunta, extraer_generadas, armar_examen

class BancoLogicTest(unittest.TestCase):
    def test_multiple(self):
        item = dict(question='¿Cuánto es 2+2?', options=['1','2','3','4'],correct_answer='4', explanation='Suma')
        normalized = normalizar_pregunta('multiple', item)
        self.assertEqual(normalized['opciones'], ['1','2','3','4'])
        self.assertEqual(armar_examen([('multiple',item)])['multiple']['questions'][0]['correct_answer'],'4')

    def test_matching(self):
        normalized = normalizar_pregunta('emparejar', {'terms':['A','B'], 'concepts':['1','2']})
        self.assertEqual(len(normalized['terminos']),2)
        data = armar_examen([('emparejar', {'terms':['A','B'],'concepts':['1','2']})])
        self.assertEqual(data['emparejar']['questions'][0]['concepts'], ['1','2'])

    def test_invalid_duplicate_options(self):
        with self.assertRaises(ValueError):
            normalizar_pregunta('multiple', {'question':'X','options':['a']*4,'correct_answer':'a'})

    def test_requires_gap(self):
        with self.assertRaises(ValueError):
            normalizar_pregunta('espacio',{'question':'Capital','correct_answer':'Quito'})

    def test_generated(self):
        items = extraer_generadas({'corta': {'questions': [{'question':'Color del cielo', 'correct_answer':'azul','explanation':'Luz'}]}})
        self.assertEqual(items[0]['tipo'],'corta')

    def test_invalid_group(self):
        with self.assertRaises(ValueError):
            extraer_generadas({'custom': {'questions': []}})

if __name__ == '__main__':
    unittest.main()
