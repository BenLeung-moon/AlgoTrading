"""
This is a submission for
FNCE30010
Algorithmic Trading
Semester 2, 2023
Project 1 - Task 1 (Induced demand-supply)
from
Student Haohong Liang
"""

from enum import Enum
from typing import List
from fmclient import Agent, Order, OrderType, OrderSide, Holding, Session
import datetime
import copy

# Student details
SUBMISSION = {"number": "1247421", "name": "HAOHONG LIANG"}

# ------ Add a variable called PROFIT_MARGIN -----
PROFIT_MARGIN = 5
LIQUIDITY_STEP = 10
SIMULATION_MARKET = 1308
CANCEL_TIME_SECOND = 2  # time to cancel order if not be traded
MAX_ORDER_UNITS = 1  # max units can send in one order


# Enum for the roles of the bot
class Role(Enum):
    BUYER = 0
    SELLER = 1


# Let us define another enumeration to deal with the type of bot
class BotType(Enum):
    PROACTIVE = 0
    REACTIVE = 1


class DSBot(Agent):
    # ------ Add an extra argument bot_type to the constructor -----
    def __init__(self, account, email, password, marketplace_id, bot_type):
        super().__init__(account, email, password, marketplace_id, name="DSBot")
        self._public_market = None
        self._private_market = None
        self._role = None
        self._bot_type = bot_type
        self._waiting_for_server = False
        self.order_ref = 0
        self.private_bought: List[Order] = []  # order list to store history from private market
        self.last_public_order: Order = Order(None)  # store last order accepted in public market
        self.mine_active_order = []  # order list to store active order in market
        # ------ Add new class variable _bot_type to store the type of the bot

    def initialised(self):
        for market_id, market in self.markets.items():
            self.inform(f"Market with ID {market_id} is {market}.")
            self.inform(f"Market {market_id} has max price of {market.max_price}.")
            if market.private_market:
                self._private_market = market
            else:
                self._public_market = market

    def role(self):
        return self._role

    def _check_bot_type(self):
        return self._bot_type

    def _is_waiting_for_server(self):
        return self._waiting_for_server

    def _order_ref_num(self):
        self.order_ref += 1
        return str(self.order_ref)

    # read list of share from private market to decide which role to play
    def _read_past_order(self):
        # cancel order if didn't be traded for a period
        try:
            for order in Order.my_current().values():
                if order.mine and \
                        (datetime.datetime.now().time() >
                         (order.date_created + datetime.timedelta(seconds=CANCEL_TIME_SECOND)).time()):
                    self._cancel_order(order)
        except IndexError:
            self.inform("Error in Cancel Order")

        # remove inactive orders
        if len(self.mine_active_order) > 0:
            for i in self.mine_active_order:
                if i not in Order.my_current().values():
                    self.mine_active_order.remove(i)

        # setting BotType
        if len(self.private_bought) > 0:
            self._bot_type = BotType.REACTIVE
            # setting role
            if self.private_bought[0].order_side == OrderSide.SELL:
                self._role = Role.SELLER
            else:
                self._role = Role.BUYER
        else:
            self._bot_type = BotType.PROACTIVE
            if self.last_public_order != Order(None):
                if self.holdings.assets[self._public_market].units_available <= 0:
                    self._role = Role.BUYER
                elif self.last_public_order.order_side == OrderSide.BUY:
                    self._role = Role.BUYER
                else:
                    self._role = Role.SELLER

    # function return a empty order with data used to compare
    def _benchmark_order(self, position):
        new_order = Order(None)
        if position == OrderSide.SELL:
            new_order.price = self._public_market.max_price
        else:
            new_order.price = self._public_market.min_price
        return new_order

    # function used to response to existed order
    def _respond_order(self, order: Order):
        new_order = copy.copy(order)
        if order.order_side == OrderSide.BUY:
            new_order.order_side = OrderSide.SELL
        else:
            new_order.order_side = OrderSide.BUY
        new_order.units = MAX_ORDER_UNITS
        new_order.ref = self._order_ref_num()

        super().send_order(new_order)
        self.mine_active_order.append(new_order)
        self._waiting_for_server = False

    # function used to place order with one time input
    def _place_order(self, orderSide: OrderSide, orderType: OrderType,
                     price: int, units: int, ref: str):

        new_order = Order.create_new(self._public_market)
        new_order.order_side = orderSide
        new_order.order_type = orderType
        new_order.price = price
        new_order.units = units
        new_order.ref = str(ref)
        super().send_order(new_order)
        self.mine_active_order.append(new_order)
        self._waiting_for_server = False

    #  function used to cancel order already exist in market
    def _cancel_order(self, order):
        cancel_order = copy.copy(order)
        cancel_order.order_type = OrderType.CANCEL
        super().send_order(cancel_order)

    #  calculate current profit
    def _get_profit(self):
        return self.holdings.cash - self.holdings.cash_initial \
               + self._public_market.max_price * (self.holdings.assets[self._private_market].units
                                                  + self.holdings.assets[self._public_market].units
                                                  - self.holdings.assets[self._private_market].units_initial -
                                                  self.holdings.assets[self._public_market].units_initial)

    # calculate profit after trade
    def _after_profit(self, order: Order):
        if order.order_side == OrderSide.BUY:
            return self.holdings.cash + (order.units * order.price) - self.holdings.cash_initial \
                   + self._public_market.max_price * (self.holdings.assets[self._private_market].units - order.units
                                                      + self.holdings.assets[self._public_market].units
                                                      - self.holdings.assets[self._private_market].units_initial -
                                                      self.holdings.assets[self._public_market].units_initial)
        else:
            return self.holdings.cash - (order.units * order.price) - self.holdings.cash_initial \
                   + self._public_market.max_price * (self.holdings.assets[self._private_market].units + order.units
                                                      + self.holdings.assets[self._public_market].units
                                                      - self.holdings.assets[self._private_market].units_initial -
                                                      self.holdings.assets[self._public_market].units_initial)

    # Calculate if a order profitable
    def _order_profitable(self, order: Order):
        return self._after_profit(order) > self._get_profit()

    def order_accepted(self, order: Order):
        if order.order_type != OrderType.CANCEL:
            self.inform(f"Accept {order.order_side.name} order {order.units} units at ${order.price / 100} "
                        f"from {order.market.name} Market: {order.ref}")
            if order.market == self._public_market and not order.mine:
                self.last_public_order = order
            if order in self.mine_active_order:
                self.mine_active_order.remove(order)

    def order_rejected(self, info, order: Order):
        self.warning(f"Order rejected {info}")

    # to check if have enough available money or asset to respond
    def _available_trade(self, order: Order):
        if order.market == self._public_market:
            if (self._order_profitable(order) and self._check_bot_type() == BotType.PROACTIVE) \
                    or self._check_bot_type() == BotType.REACTIVE \
                    and (order.price + LIQUIDITY_STEP <= self._public_market.max_price
                         and order.price - LIQUIDITY_STEP >= self._public_market.min_price) \
                    and len(Order.my_current().items()) == 0:
                if order.order_side == OrderSide.BUY and self.role() == Role.SELLER \
                        and self.holdings.assets[order.market].units_available >= MAX_ORDER_UNITS:
                    self._print_trade_opportunity(order, True)
                    return True
                elif order.order_side == OrderSide.SELL and self.role() == Role.BUYER \
                        and self.holdings.cash_available >= MAX_ORDER_UNITS * order.price:
                    self._print_trade_opportunity(order, True)
                    return True
                else:
                    return False
        elif order.market == self._private_market and len(Order.my_current().items()) == 0:
            if order.order_side == OrderSide.BUY and \
                    self.holdings.assets[order.market].units_available >= MAX_ORDER_UNITS:
                return True
            elif order.order_side == OrderSide.SELL and \
                    self.holdings.cash_available >= order.price * MAX_ORDER_UNITS:
                return True
            return False
        else:
            self._print_trade_opportunity(order, False)
            return False

    def received_orders(self, orders: List[Order]):
        lowest_sell = self._benchmark_order(OrderSide.SELL)
        highest_buy = self._benchmark_order(OrderSide.BUY)

        self._waiting_for_server = True

        cur_order_dict = Order.current().items()

        # iterating order book
        for order_id, order in cur_order_dict:

            # renew order book price
            if order.order_side == OrderSide.BUY and order.price > highest_buy.price \
                    and order.market == self._public_market and not order.mine:
                highest_buy = order
            if order.order_side == OrderSide.SELL and order.price < lowest_sell.price \
                    and order.market == self._public_market and not order.mine:
                lowest_sell = order

            # receiving private order
            try:
                if order.market == self._private_market and self._available_trade(order) \
                        and self._is_waiting_for_server() and not order.mine \
                        and order not in self.private_bought \
                        and order_id in Order.current().keys() \
                        and len(Order.my_current()) == 0:

                    if order.order_side == OrderSide.BUY:
                        self._respond_order(order)
                        self.private_bought.insert(0, order)

                    elif order.order_side == OrderSide.SELL:
                        self._respond_order(order)
                        self.private_bought.insert(0, order)

            except BaseException:
                self.inform("Error in Receiving Private Order")

            self._read_past_order()

        # proactive bot response to public market
        self._read_past_order()
        spread = lowest_sell.price - highest_buy.price
        try:

            if self._is_waiting_for_server() and self._check_bot_type() == BotType.PROACTIVE \
                    and len(self.mine_active_order) == 0 and len(Order.my_current()) == 0:
                if self.last_public_order.fm_id != Order(None).fm_id:
                    if self.role() == Role.BUYER and self._available_trade(self.last_public_order) \
                            and self._order_profitable(lowest_sell):
                        self._place_order(OrderSide.BUY, OrderType.LIMIT, self.last_public_order.price - PROFIT_MARGIN,
                                          MAX_ORDER_UNITS, self._order_ref_num())
                    if self.role() == Role.SELLER and self._available_trade(self.last_public_order) \
                            and self._order_profitable(highest_buy):
                        self._place_order(OrderSide.SELL, OrderType.LIMIT, self.last_public_order.price + PROFIT_MARGIN,
                                          MAX_ORDER_UNITS, self._order_ref_num())

                elif spread > 100:
                    if self.role() == Role.BUYER and self._available_trade(highest_buy):
                        self._place_order(OrderSide.BUY, OrderType.LIMIT, highest_buy.price + LIQUIDITY_STEP,
                                          MAX_ORDER_UNITS,
                                          self._order_ref_num())

                    if self.role() == Role.SELLER and self._available_trade(lowest_sell):
                        self._place_order(OrderSide.SELL, OrderType.LIMIT, lowest_sell.price - LIQUIDITY_STEP,
                                          MAX_ORDER_UNITS,
                                          self._order_ref_num())
        except BaseException:
            self.inform("Error in Proactive response")

        # reactive type trading strategy
        try:

            if self._check_bot_type() == BotType.REACTIVE and self._is_waiting_for_server() \
                    and len(self.mine_active_order) == 0 and len(Order.my_current()) == 0:
                if self.role() == Role.SELLER \
                        and highest_buy.price > self.private_bought[0].price + PROFIT_MARGIN \
                        and self._available_trade(highest_buy):
                    if self.private_bought[0].price - PROFIT_MARGIN < self._public_market.min_price:
                        self._place_order(OrderSide.SELL, OrderType.LIMIT,
                                          self.private_bought[0].price,
                                          MAX_ORDER_UNITS, self._order_ref_num())
                        self.private_bought.pop(0)
                    else:
                        self._place_order(OrderSide.SELL, OrderType.LIMIT,
                                          self.private_bought[0].price - PROFIT_MARGIN,
                                          MAX_ORDER_UNITS, self._order_ref_num())
                        self.private_bought.pop(0)


                elif self.role() == Role.BUYER \
                        and lowest_sell.price < self.private_bought[0].price - PROFIT_MARGIN \
                        and self._available_trade(lowest_sell):
                    if self.private_bought[0].price + PROFIT_MARGIN > self._public_market.max_price:
                        self._place_order(OrderSide.BUY, OrderType.LIMIT,
                                          self.private_bought[0].price,
                                          MAX_ORDER_UNITS, self._order_ref_num())
                        self.private_bought.pop(0)
                    else:
                        self._place_order(OrderSide.BUY, OrderType.LIMIT,
                                          self.private_bought[0].price + PROFIT_MARGIN,
                                          MAX_ORDER_UNITS, self._order_ref_num())
                        self.private_bought.pop(0)

        except RuntimeError:
            self.inform("Error Reactive Strategy")

    def _print_trade_opportunity(self, other_order, can_trade):
        if can_trade:
            self.inform(f"Have Sent a Order as {self.role().name} with profitable order {other_order}")
        else:
            if (other_order.price + PROFIT_MARGIN > other_order.market.max_price
                    or other_order.price - PROFIT_MARGIN < other_order.market.min_price):
                self.inform(f"Unable to Respond {other_order} since Order Price is over or below the Bound")
            elif other_order.mine:
                pass
            elif self.role() == Role.BUYER:
                self.inform(f"Unable to Respond {other_order} since a {self.role().name} bot has ran out of cash")
            else:
                self.inform(f"Unable to Respond {other_order} since a {self.role().name} bot has ran out of asset")

    def received_holdings(self, holdings: Holding):
        self.inform(f"My available cash is {holdings.cash_available}")
        for _id, asset in holdings.assets.items():
            self.inform(f"Assets {asset.market}: Available {asset.units_available}")

    def received_session_info(self, session: Session):
        self.inform(f"Market is now closed: {session.is_closed}")
        self.inform(f"Market is now open: {session.is_open}")

    def pre_start_tasks(self):
        pass


if __name__ == "__main__":
    FM_ACCOUNT = "jocund-value"
    FM_EMAIL = "haohong@student.unimelb.edu.au"
    FM_PASSWORD = "1247421"
    MARKETPLACE_ID = SIMULATION_MARKET

    ds_bot = DSBot(FM_ACCOUNT, FM_EMAIL, FM_PASSWORD, MARKETPLACE_ID, BotType.REACTIVE)
    ds_bot.run()
