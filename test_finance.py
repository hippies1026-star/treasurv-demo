import copy
import math
import unittest
from data import demo
from finance_engine import analyze, forecast, validate, validate_plan
from agent import ask


class FinanceTests(unittest.TestCase):
    def test_allocation_never_consumes_floor(self):
        for stress in (0, 15, 50, 100):
            for allocation in (0, 70, 100):
                d=demo()
                d.update(revenue_stress=stress, allocation=allocation)
                a=analyze(d)
                self.assertLessEqual(a['principal'],a['capacity'])
                self.assertGreaterEqual(a['capacity'],0)
                if a['gap']==0:
                    # Even if the entire chosen principal is unavailable, protective
                    # monthly balances must preserve the emergency reserve.
                    self.assertGreaterEqual(min([a['available']]+[r['balance'] for r in a['protective'][:d['target']]])-a['principal']+1e-6,a['reserve'])

    def test_future_funding_does_not_lower_floor(self):
        d=demo()
        a=analyze(d)
        d['plans'][-1]['amount']=10_000_000_000
        b=analyze(d)
        self.assertEqual(a['floor'],b['floor'])
        self.assertGreater(b['base'][-1]['balance'],a['base'][-1]['balance'])

    def test_prefix_deficit_not_just_final_month(self):
        d=demo()
        d.update(inflow=100,outflow=0,buffer=0,revenue_stress=0,cost_stress=0,target=3)
        d['plans']=[{'id':'a','name':'장비','kind':'일회성 지출','month':1,'amount':250,'recurring':False,'confirmed':True}]
        self.assertEqual(analyze(d)['floor'],150)

    def test_recurring_and_delayed_funding(self):
        d=demo()
        rows=forecast(d,funding_delay=3)
        self.assertEqual(rows[8]['funding'],0)
        self.assertEqual(rows[11]['funding'],300_000_000)
        self.assertEqual(rows[1]['outflow'],120_000_000)
        self.assertEqual(rows[2]['outflow'],126_000_000)
        self.assertEqual(rows[5]['outflow'],166_000_000)

    def test_zero_cash_and_no_burn(self):
        d=demo()
        d.update(cash=0,restricted=0)
        self.assertEqual(analyze(d)['principal'],0)
        d.update(cash=100,inflow=0,outflow=0,buffer=0,plans=[])
        a=analyze(d)
        self.assertEqual(a['floor'],0)
        self.assertIsNone(a['shortfall'])

    def test_interest_is_incremental_simple_not_compounded(self):
        d=demo()
        d.update(rate=4,baseline_rate=1,tenor=3)
        a=analyze(d)
        self.assertAlmostEqual(a['incremental'],a['principal']*.03)
        self.assertAlmostEqual(a['tenor_interest'],a['principal']*.01)

    def test_invalid_inputs_rejected(self):
        for value in (-1,float('nan'),float('inf'),True,'100'):
            d=demo(); d['cash']=value
            with self.assertRaises(ValueError):validate(d)
        d=demo();d['restricted']=d['cash']+1
        with self.assertRaises(ValueError):validate(d)

    def test_local_summary_without_key(self):
        text,proposal=ask('질문',demo(),[],'','unused')
        self.assertIn('AI 응답 아님',text)
        self.assertIsNone(proposal)


if __name__=='__main__':unittest.main()
