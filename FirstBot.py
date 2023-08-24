from typing import List
from fmclient import Agent, Order, OrderType, OrderSide, Holding, Session, Market
from fmclient.data.orm.holding import Holding
from fmclient.data.orm.order import Order
from fmclient.data.orm.session import Session
import datetime
import copy
import sys

MY_ACCOUNT = "jocund-value"
MY_EMAIL = "haohong@student.unimelb.edu.au"
MY_PASSWORD = "1247421"
SIMULATION_MARKET = 1308
WIDGET_MARKET = 1304
SINGLE_PRACTICE_MARKET = 1300
THRESHOLD = 20  # profit margin to make a trade
CANCEL_TIME_SECOND = 5  # time to cancel order if not be traded


class FirstBot(Agent):
    """
    Attributes:
        threshold: an int used to store profit margin

    """

    def __init__(self, account: str, email: str, password: str, marketplace_id: int,
                 name: str = None, enable_ws: bool = True):
        super().__init__(account, email, password, marketplace_id, name, enable_ws)
        self.public_market = None
        self.private_market = None
        self._waiting_for_server = True
        self.threshold = THRESHOLD
        self.averageHoldingPrice = 0

    def initialised(self):
        for market_id, market in self.markets.items():
            self.inform(f"Market with ID {market_id} is {market}.")
            self.inform(f"Market {market_id} has max price of {market.max_price}.")
            if market.private_market:
                self.private_market = market
            else:
                self.public_market = market

    # function used to response to existed order
    def respond_order(self, order: Order):
        new_order = copy.copy(order)
        if order.order_side == OrderSide.BUY:
            new_order.order_side = OrderSide.SELL
        else:
            new_order.order_side = OrderSide.BUY

        super().send_order(new_order)
        self._waiting_for_server = False

    # function used to place order with one time input
    def place_order(self, orderSide: OrderSide, orderType: OrderType,
                    price: int, units: int, ref: str):

        new_order = Order.create_new(self.public_market)
        new_order.order_side = orderSide
        new_order.order_type = orderType
        new_order.price = price
        new_order.units = units
        new_order.ref = ref
        super().send_order(new_order)
        self._waiting_for_server = False

    #  function used to cancel order already exist in market
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
            self.averageHoldingPrice = self.holdings.cash_available / asset.units_available

    def received_orders(self, orders: List[Order]):
        # pass
        num_my_order = 0
        lowest_sell = sys.maxsize
        highest_buy = -sys.maxsize + 1

        # iterating order book
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

            # response to public/private market
            if order.market == self.public_market and self._waiting_for_server:
                if order.order_side == OrderSide.BUY:
                    if order.price - self.threshold > self.averageHoldingPrice:
                        self.respond_order(order)

                if order.order_side == OrderSide.SELL:
                    if order.price + self.threshold < self.averageHoldingPrice:
                        self.respond_order(order)

            if order.market == self.private_market and self._waiting_for_server \
                    and not order.mine:
                if order.order_side == OrderSide.BUY:
                    self.respond_order(order)
                    self.inform(f"Accept buy order with {order.units} units at ${order.price}")

                if order.order_side == OrderSide.SELL:
                    self.respond_order(order)
                    self.inform(f"Accept sell order with {order.units} units at ${order.price}")

            # cancel order if didn't be traded for a period
            # can replace on the proactive
            if order.mine and \
                    (datetime.datetime.now().time() >
                     (order.date_created + datetime.timedelta(seconds=CANCEL_TIME_SECOND)).time())\
                    and not order.has_traded:
                self.cancel_order(order)
                self._waiting_for_server = True

        #  calculate spread and check whether liquid the orders
        spread = lowest_sell - highest_buy
        if spread <= 30 and self._waiting_for_server and self.markets == self.public_market:
            self.place_order(OrderSide.SELL, OrderType.LIMIT, highest_buy + 5,
                             2, "liquidity")

        if spread > 100 and self._waiting_for_server and self.markets == self.public_market:
            self.place_order(OrderSide.SELL, OrderType.LIMIT, lowest_sell - 100,
                             2, "liquidity")

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
        self.execute_periodically(self.received_holdings(), 1)
        pass


if __name__ == "__main__":
    bot = FirstBot(MY_ACCOUNT, MY_EMAIL, MY_PASSWORD, WIDGET_MARKET)
    bot.run()
