from typing import List
from fmclient import Agent, Order, OrderType, OrderSide, Holding, Session
from fmclient.data.orm.holding import Holding
from fmclient.data.orm.order import Order
from fmclient.data.orm.session import Session
import copy

MY_ACCOUNT = "jocund-value"
MY_EMAIL = "haohong@student.unimelb.edu.au"
MY_PASSWORD = "1247421"
WIDGET_MARKET = 1303
SINGLE_PRACTICE_MARKET = 1300


class FirstBot(Agent):

    def __init__(self, account: str, email: str, password: str, marketplace_id: int,
                 name: str = None, enable_ws: bool = True):
        super().__init__(account, email, password, marketplace_id, name, enable_ws)
        self.order_sent = False
        self.public_market = None
        self.private_market = None
        self._waiting_for_server = True

    def initialised(self):
        for market_id, market in self.markets.items():
            self.inform(f"Market with ID {market_id} is {market}.")
            self.inform(f"Market {market_id} has max price of {market.max_price}.")
            if market.private_market:
                self.private_market = market
            else:
                self.public_market = market

    def making_order(self):
        pass

    def received_holdings(self, holdings: Holding):
        self.inform(f"My settled cash is {holdings.cash}")
        self.inform(f"My available cash is {holdings.cash}")
        for _id, asset in holdings.assets.items():
            self.inform(f"Asset {asset.market}: settled {asset.units}")
            self.inform(f"Assets {asset.market}: Available {asset.units_available}")

    def received_orders(self, orders: List[Order]):
        num_my_order = 0
        for order_id, order in Order.current().items():
            if order.market == self.public_market and order.mine:
                num_my_order += 1

            if num_my_order == 0 and not self._waiting_for_server:

                self._waiting_for_server = True
                pass

            # my order check

            # response to public/private market
            if order.market == self.public_market:
                if order.side == OrderSide.BUY:
                    pass

                pass

            # if order.market == self.private_market:
            #     if order.order_side == OrderSide.BUY:
            #         new_order = Order.create_new(self.private_market)
            #         new_order.order_side = OrderSide.SELL
            #         new_order.order_type = OrderType.LIMIT
            #         new_order.price = order.price
            #         new_order.units = order.units
            #         new_order.ref = "private"
            #         new_order.owner_or_target = "M000"
            #         super().send_order(new_order)

        # # send an order to market
        # if not self.order_sent:
        #     order = Order.create_new(self.public_market)
        #     order.price = 100
        #     order.order_side = OrderSide.SELL
        #     order.units = 1
        #     order.order_type = OrderType.LIMIT
        #     order.ref = ""
        #     super().send_order(order)
        #     self.order_sent = True
        #
        # # iterate orders book
        # for order in orders:
        #     self.inform(f"{order}")
        #   #cancel order
        #     if order.mine:
        #         self.inform(f"This is my own order! {order}")
        #         cancel_order = copy.copy(order)
        #         cancel_order.order_type = OrderType.CANCEL
        #         super().send_order(cancel_order)
        #
        #     if order.order_side == OrderSide.BUY:
        #         pass
        #     elif order.order_side == OrderSide.SELL:
        #         pass
        #
        #     if order.order_type == OrderType.LIMIT:
        #         pass
        #     elif order.order_type == OrderType.CANCEL:
        #         pass
        #
        # for order_id, order in Order.current().items():
        #     self.inform(f"{order}")

    def order_accepted(self, order: Order):
        self.inform(f"Order accepted: {order.ref}")

    def order_rejected(self, info: dict, order: Order):
        self.warning(f"Order rejected {info}")

    def received_session_info(self, session: Session):
        self.inform(f"Market is now closed: {session.is_closed}")
        self.inform(f"Market is now open: {session.is_open}")

    def pre_start_tasks(self):
        # #can call any method in the class periodically
        # self.execute_periodically()
        pass

if __name__ == "__main__":
    bot = FirstBot(MY_ACCOUNT, MY_EMAIL, MY_PASSWORD, WIDGET_MARKET)
    bot.run()
