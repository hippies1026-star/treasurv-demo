"""Run with python -m unittest test_ui -v."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class UITests(unittest.TestCase):
    def start(self):
        app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=30).run()
        self.assertEqual(len(app.exception),0)
        next(b for b in app.button if b.label=='데모 시작하기 →').click().run()
        self.assertEqual(len(app.exception),0)
        return app

    def test_all_pages(self):
        app=self.start()
        for page in ['대시보드','현금 현황','현금흐름 예측','보호할 현금','사업계획','시나리오 비교','운용 시뮬레이터','AI CFO','데이터 연결','보고서','팀','변경 기록','설정']:
            app.button(key='nav_'+page).click().run()
            self.assertEqual(len(app.exception),0,page)

    def test_plan_policy_and_invalidation(self):
        app=self.start()
        app.button(key='nav_사업계획').click().run()
        app.text_input[0].set_value('테스트 채용')
        next(b for b in app.button if b.label=='계획 추가').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.session_state['data']['plans']),4)
        app.button(key='nav_운용 시뮬레이터').click().run()
        next(b for b in app.button if b.label=='이 조건으로 정책 초안 만들기').click().run()
        next(b for b in app.button if b.label=='초안 승인 · 데모').click().run()
        self.assertIsNotNone(app.session_state['approved'])
        app.button(key='nav_데이터 연결').click().run()
        app.number_input[0].set_value(100000.0)
        next(b for b in app.button if b.label=='데모 데이터 저장').click().run()
        self.assertEqual(app.session_state['data']['cash'],1_000_000_000)
        from finance_engine import fingerprint
        self.assertNotEqual(app.session_state['approved']['fingerprint'],fingerprint(app.session_state['data']))
        self.assertEqual(len(app.exception),0)


if __name__=='__main__':unittest.main()
