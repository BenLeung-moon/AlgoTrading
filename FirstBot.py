from typing import List
from fmclient import Agent, Order, OrderType, OrderSide, Holding, Session
from fmclient.data.orm.holding import Holding
from fmclient.data.orm.order import Order
from fmclient.data.orm.session import Session
import datetime
import copy
import sys

MY_ACCOUNT = "jocund-value"
MY_EMAIL = "haohong@student.unimelb.edu.au"
MY_PASSWORD = "1247421"
WIDGET_MARKET = 1304
SINGLE_PRACTICE_MARKET = 1300
THRESHOLD = 50  # profit margin to make a trade
CANCEL_TIME_SECOND = 5  # time to cancel order if not be traded


class FirstBot(Agent):

    def __init__(self, account: str, email: str, password: str, marketplace_id: int,
                 name: str = None, enable_ws: bool = True):
        super().__init__(account, email, password, marketplace_id, name, enable_ws)
        self.order_sent = False
        self.public_market = None
        self.private_market = None
        self._waiting_for_server = True
        self.threshold = THRESHOLD

    def initialised(self):
        for market_id, market in self.markets.items():
            self.inform(f"Market with ID {market_id} is {market}.")
            self.inform(f"Market {market_id} has max price of {market.max_price}.")
            if market.private_market:
                self.private_market = market
            else:
                self.public_market = market

    def accept_order(self, order: Order):
        new_order = copy.copy(order)
        new_order.order_side = -order.order_side
        super().send_order(new_order)

    # function used to make public order with one time input
    def place_order(self, orderSide: OrderSide, orderType: OrderType,
                    price: int, units: int, ref: str, isPrivate: bool
                    , owner_or_target: str):
        if isPrivate:
            new_order = Order.create_new(self.private_market)
        else:
            new_order = Order.create_new(self.public_market)

        new_order.order_side = orderSide
        new_order.order_type = orderType
        new_order.price = price
        new_order.units = units
        new_order.ref = ref
        if isPrivate:
            new_order.owner_or_target = owner_or_target
        super().send_order(new_order)

    #  function used to cancel order already exist in market
    #  order base
    def cancel_order(self, order):
        cancel_order = copy.copy(order)
        cancel_order.order_type = OrderType.CANCEL
        super().send_order(cancel_order)

    def received_holdings(self, holdings: Holding):
        self.inform(f"My settled cash is {holdings.cash}")
        self.inform(f"My available cash is {holdings.cash}")
        for _id, asset in holdings.assets.items():
            self.inform(f"Asset {asset.market}: settled {asset.units}")
            self.inform(f"Assets {asset.market}: Available {asset.units_available}")

    def received_orders(self, orders: List[Order]):
        num_my_order = 0
        lowest_sell = sys.maxsize
        highest_buy = -sys.maxsize - 1

        for order_id, order in Order.current().items():

            # renew order book price
            if order.order_side == OrderSide.BUY and order.price > highest_buy:
                highest_buy = order.price
            elif order.order_side == OrderSide.SELL and order.price < lowest_sell:
                lowest_sell = order.price

            if order.market == self.public_market and order.mine:
                num_my_order += 1

            if num_my_order == 0 and not self._waiting_for_server:
                self._waiting_for_server = True
                # self.place_order(OrderSide.BUY, OrderType.LIMIT,
                #                  500, 1, "ref", False, "")

            # iterating order
            # response to public/private market
            if order.market == self.public_market and self._waiting_for_server:
                if order.order_side == OrderSide.BUY:
                    pass

                if order.order_side == OrderSide.SELL:
                    pass

            if order.market == self.private_market:
                if order.order_side == OrderSide.BUY:
                    self.accept_order(order)

                if order.order_side == OrderSide.SELL:
                    self.accept_order(order)

            # cancel order if didn't be traded for a period
            if order.mine and \
                    (datetime.datetime.now().time() >
                     (order.date_created + datetime.timedelta(seconds=CANCEL_TIME_SECOND)).time()):
                self.cancel_order(order)

    def order_accepted(self, order: Order):
        self.inform(f"Order accepted: {order.ref}")
        self._waiting_for_server = False

    def order_rejected(self, info: dict, order: Order):
        self.warning(f"Order rejected {info}")
        self._waiting_for_server = False

    def received_session_info(self, session: Session):
        self.inform(f"Market is now closed: {session.is_closed}")
        self.inform(f"Market is now open: {session.is_open}")

    def pre_start_tasks(self):
        # #can call any method in the class periodically
        # self.execute_periodically()
        pass


if __name__ == "__main__":
    bot = FirstBot(MY_ACCOUNT, MY_EMAIL, MY_PASSWORD, SINGLE_PRACTICE_MARKET)
    bot.run()
