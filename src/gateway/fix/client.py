import quickfix as fix
import quickfix44 as fix44
import time
import uuid

CFG_PATH = "fix.cfg"


class Application(fix.Application):
    def onCreate(self, sessionID):
        print("Session created:", sessionID)

    def onLogon(self, sessionID):
        print("Successfully logged on:", sessionID)

        # Send an example LIMIT BUY order for AAPL
        self.send_test_order(sessionID)

    def onLogout(self, sessionID):
        print("Logged out:", sessionID)

    def toAdmin(self, message, sessionID):
        print("To Admin:", message)

    def fromAdmin(self, message, sessionID):
        print("From Admin:", message)

    def toApp(self, message, sessionID):
        print("To App:", message)

    def fromApp(self, message, sessionID):
        print("From App (Execution Report):", message)
        self.on_execution_report(message, sessionID)

    def send_test_order(self, sessionID):
        """Send a simple example order: BUY 1 AAPL @ 150.00"""
        order = fix44.NewOrderSingle(
            fix.ClOrdID(str(uuid.uuid4())),
            fix.Side(fix.Side_BUY),
            fix.TransactTime(),
            fix.OrdType(fix.OrdType_LIMIT)
        )

        # Required fields
        order.setField(fix.Symbol("AAPL"))
        order.setField(fix.OrderQty(1))
        order.setField(fix.Price(150.00))
        order.setField(fix.TimeInForce(fix.TimeInForce_DAY))
        order.setField(fix.Account("YOUR_PAPER_ACCOUNT_ID"))  # <-- Replace

        print("Sending Order:", order)

        fix.Session.sendToTarget(order, sessionID)

    def on_execution_report(self, message, sessionID):
        """Handle fills, partial fills, rejects, etc."""
        try:
            exec_type = message.getField(150)
            ord_status = message.getField(39)
            symbol = message.getField(55)
            print(f"[ExecutionReport] Symbol={symbol}, ExecType={exec_type}, OrdStatus={ord_status}")
        except Exception as e:
            print("Error parsing execution report:", e)


def main():
    settings = fix.SessionSettings(CFG_PATH)
    app = Application()
    store_factory = fix.FileStoreFactory(settings)
    log_factory = fix.FileLogFactory(settings)
    initiator = fix.SocketInitiator(app, store_factory, settings, log_factory)

    try:
        initiator.start()
        print("FIX Initiator started. Waiting for logon...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        initiator.stop()


if __name__ == "__main__":
    main()
