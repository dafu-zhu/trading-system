from typing import Dict
from enum import Enum

"""
|34=12|35=D|38=10|40=1|49=SENDER|52=20230613-14:01:37.330|54=1|55=SPY|56=ALPACA|59=1|10=030|
"""

class FixTag(Enum):
    BEGIN_STRING = "8"
    BODY_LENGTH = "9"
    ACCOUNT = "1"
    CL_ORD_ID = "11"
    MSG_SEQ_NUM = "34"
    MSG_TYPE = "35"
    ORDER_QTY = "38"
    ORD_TYPE = "40"
    SENDER_COMP_ID = "49"
    SENDING_TIME = "52"
    SIDE = "54"
    SYMBOL = "55"
    TARGET_COMP_ID = "56"
    TIME_IN_FORCE = "59"
    CHECK_SUM = "10"


class FixMsgType(Enum):
    LOGON = "A"
    HEART_BEAT = "0"
    TEST_REQUEST = "1"
    RESEND_REQUEST = "2"
    REJECT = "3"
    SEQUENCE_RESET = "4"
    LOGOUT = "5"
    NEW_ORDER_SINGLE = "D"
    EXECUTION_REPORT = "8"
    ORDER_CANCEL_REQUEST = "F"
    ORDER_CANCEL_REJECT = "9"


class FixParser:
    """
    Parse and validate incoming FIX message
    """

    REQUIRED_TAGS = {
        FixTag.BEGIN_STRING.value,
        FixTag.MSG_TYPE.value,
        FixTag.CHECK_SUM.value
    }

    ORDER_REQUIRED_TAGS = {
        FixTag.SYMBOL.value,
        FixTag.SIDE.value,
        FixTag.ORD_TYPE.value,
        FixTag.ORDER_QTY.value
    }

    def __init__(self, delimiter: str, validate: bool = True):
        self.delimiter = delimiter
        self.validate = validate

    def parse(self, message: str) -> dict:
        if not message:
            raise ValueError("Empty message")

        fields = message.split(self.delimiter)
        parsed = {}
        for field in fields:
            if not field:
                continue
            key, value = field.split('=', 1)
            parsed[key] = value

        if self.validate:
            self.validate_msg(parsed)

        return parsed

    def validate_msg(self, parsed: Dict[str, str]) -> None:
        missing = self.REQUIRED_TAGS - set(parsed.keys())
        if missing:
            raise ValueError("Missing required tags in message")

        msg_type = parsed.get(FixTag.MSG_TYPE.value)
        if msg_type == FixMsgType.NEW_ORDER_SINGLE.value:
            missing = self.ORDER_REQUIRED_TAGS - set(parsed.keys())
            if missing:
                raise ValueError("Missing order required tags in message")



if __name__ == "__main__":
    msg = "8=FIX.4.2|35=D|55=AAPL|54=1|38=100|40=2|10=128"
    print(FixParser("|").parse(msg))
