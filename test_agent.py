import io
import json
import unittest
from unittest.mock import patch
from agent import ask
from data import demo


class AgentTests(unittest.TestCase):
    def test_tool_proposal_is_not_applied(self):
        plan={"name":"추가 채용","kind":"채용","month":3,"amount":12000000,"recurring":True,"confirmed":True}
        replies=[{"choices":[{"message":{"role":"assistant","content":None,"tool_calls":[
            {"id":"tool1","type":"function","function":{"name":"propose_plan","arguments":json.dumps(plan)}}]}}]},
            {"choices":[{"message":{"role":"assistant","content":"계획 반영 버튼으로 확인하세요."}}]}]
        def mock_response(*args,**kwargs):
            return io.BytesIO(json.dumps(replies.pop(0)).encode())
        d=demo()
        before=json.dumps(d,sort_keys=True)
        with patch('urllib.request.urlopen',side_effect=mock_response):
            answer,proposal=ask('계획 추가',d,[],'test-key','test-model')
        self.assertEqual(proposal,plan)
        self.assertEqual(json.dumps(d,sort_keys=True),before)
        self.assertIn('확인',answer)

    def test_invalid_proposal_is_rejected(self):
        replies=[{"choices":[{"message":{"role":"assistant","tool_calls":[
            {"id":"tool1","type":"function","function":{"name":"propose_plan","arguments":"{}"}}]}}]},
            {"choices":[{"message":{"role":"assistant","content":"정보를 더 알려주세요."}}]}]
        with patch('urllib.request.urlopen',side_effect=lambda *a,**k:io.BytesIO(json.dumps(replies.pop(0)).encode())):
            _,proposal=ask('채용',demo(),[],'test-key','test-model')
        self.assertIsNone(proposal)


if __name__=='__main__':unittest.main()
