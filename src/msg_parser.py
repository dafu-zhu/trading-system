from enum import Enum

class MsgType(Enum):
    Heartbeat = 0
    TestRequest = 1
    ResendRequest = 2
    Reject = 3
    SequenceReset = 4
    Logout = 5
    Logon = "A"

class TagValue(Enum):
    BeginString = 8
    BodyLength = 9
    MsgType = 35
    SenderCompID = 49
    TargetCompID = 56
    MsgSeqNum = 34
    SendingTime = 52
    Symbol = 55
    Side = 54
    OrdType = 40
    ClOrdID = 11
    OrdStatus = 39
    ExecType = 150
    TransactTime = 60
