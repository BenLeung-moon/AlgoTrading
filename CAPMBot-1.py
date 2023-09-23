"""
This is a template bot for  the CAPM Task.
"""
from enum import Enum
from typing import List
from fmclient import Agent, Order, OrderType, OrderSide, Holding, Session, Market
import datetime
import copy

# Submission details
SUBMISSION = {"student_number": "1247421", "name": "HAOHONG LIANG"}

FM_ACCOUNT = "jocund-value"
FM_EMAIL = "haohong@student.unimelb.edu.au"
FM_PASSWORD = "1247421"
MARKETPLACE_ID = 1316  # replace this with the marketplace id
SIMULATION_MARKET = 1323
MAX_ORDER_UNITS = 1  # max units can send in one order
ORDER_OVERDUE_SECOND = 8
LOW_CASH_THRESHOLD = 1500  # threshold to sell note


def _get_stock_code(name):
    """
    returns stock index for list
    :param name: string of stock name
    """
    if name == "A":
        return Stock.A.value
    elif name == "B":
        return Stock.B.value
    elif name == 'C':
        return Stock.C.value
    elif name == 'Note':
        return Stock.NOTE.value


def _get_prospective_holdings(holdings, cash, order):
    """
    Returns the portfolio and cash if execute the order
    :param holdings: list of portfolio
    :param cash: value of holding cash
    :param order: order will be executed
    :return prospect_stock: list of stock after execution
    :return prospect_cash: value of cash after execution
    """
    prospect_holding = holdings
    prospect_cash = cash

    if order.order_side == OrderSide.BUY:
        prospect_holding[_get_stock_code(order.market.item)] -= order.units
        prospect_cash += order.units * order.price
    else:
        prospect_holding[_get_stock_code(order.market.item)] += order.units
        prospect_cash -= order.units * order.price

    return prospect_holding, prospect_cash


class Stock(Enum):
    A = 0
    B = 1
    C = 2
    NOTE = 3


class CAPMBot(Agent):

    def __init__(self, account, email, password, marketplace_id, risk_penalty=0.001, session_time=20):
        """
        Constructor for the Bot
        :param account: Account name
        :param email: Email id
        :param password: password
        :param marketplace_id: id of the marketplace
        :param risk_penalty: Penalty for risk
        :param session_time: Total trading time for one session
        """
        super().__init__(account, email, password, marketplace_id, name="CAPM Bot")
        self._payoffs_var = {'A': {'A': 15625,
                                   'B': -46875,
                                   'C': -140625,
                                   'N': 0},
                             'B': {'B': 15625,
                                   'C': 9375,
                                   'N': 0},
                             'C': {'C': 15625,
                                   'N': 0},
                             'N': 0
                             }
        self._payoffs = {}
        self.order_ref = 0
        self._risk_penalty = risk_penalty
        self._session_time = session_time
        self._market_ids = {}
        self._stock_holding = [0, 0, 0, 0]
        self._stock_available = [0, 0, 0, 0]
        self._cash_available = 0
        self._best_price = {}
        self._sent_order = {}
        self._waiting_for_order = True
        self._waiting_for_latest_holding = True
        self._market_open = False

    def initialised(self):
        # Extract payoff distribution for each security
        for market_id, market_info in self.markets.items():
            security = market_info.item
            self._market_ids[security] = market_id
            description = market_info.description
            self._payoffs[security] = [int(a) for a in description.split(",")]
            self._best_price[security] = {}

        self.inform("Bot initialised, I have the payoffs for the states.")

    def _get_cash_available(self):
        return self.holdings.cash_available

    def _get_cash(self):
        """
        getter of bot cash
        :return: value of holding cash
        """
        return self.holdings.cash

    def _get_risk_penalty(self):
        """
        getter of _risk_penalty
        :return: value of _risk_penalty
        """
        return self._risk_penalty

    def _get_stock_available(self):
        """
        getter of _stock_available
        : return: list of _stock_available
        """
        return self._stock_available

    def _get_stock_holding(self):
        """
        getter of _stock_holding
        :return: list of _stock_holding
        """
        return self._stock_holding

    def _order_ref_num(self):
        self.order_ref += 1
        return str(self.order_ref)

    def _states_sync(self):
        """
        return True when the bot have synced data
        """
        return (not self._waiting_for_latest_holding) and self._waiting_for_order and self._market_open

    def _compute_expected_payoff(self, holdings, cash):
        """
        Return the expected value of payoff
        :param holdings: list of holdings
        :return: value of expected payoff
        """
        return cash + 0.25 * (
                holdings[Stock.A.value] * sum(self._payoffs['A']) + holdings[Stock.B.value] * sum(self._payoffs['B']) +
                holdings[Stock.C.value] * sum(self._payoffs['C']) + holdings[Stock.NOTE.value] * sum(
            self._payoffs['Note']))

    def _compute_var_payoff(self, holdings):
        """
        Return the variance of expected payoff
        :param holdings: list of holdings
        :return: value of variance of payoff
        """
        return pow(holdings[Stock.A.value], 2) * self._payoffs_var['A']['A'] \
               + pow(holdings[Stock.B.value], 2) * self._payoffs_var['B']['B'] \
               + pow(holdings[Stock.C.value], 2) * self._payoffs_var['C']['C'] \
               + 2 * holdings[Stock.A.value] * holdings[Stock.B.value] * self._payoffs_var['A']['B'] \
               + 2 * holdings[Stock.A.value] * holdings[Stock.C.value] * self._payoffs_var['A']['C'] \
               + 2 * holdings[Stock.B.value] * holdings[Stock.C.value] * self._payoffs_var['B']['C']

    def _is_valid_order(self, orders: [Order]):
        """
        Return true if the order can be responded or sent
        : param order: list of order will be executed
        : return: Boolean
        """
        # compute all order needs
        stocks = [0, 0, 0, 0]
        cash = 0
        try:
            for order in orders:
                if order.mine is False:
                    if order.order_side == OrderSide.BUY:
                        stocks[_get_stock_code(order.market.item)] += order.units
                    else:
                        cash += order.units * order.price
                elif order.mine is True:
                    if order.order_side == OrderSide.SELL:
                        stocks[_get_stock_code(order.market.item)] += order.units
                    else:
                        cash += order.units * order.price

            # check whether have enough stocks and cash
            for i in range(len(stocks)):
                if stocks[i] > self._get_stock_available()[i]:
                    return False

            if cash > self._get_cash_available():
                return False

            return True
        except IndexError:
            self.inform("_is_valid_order raise error")

    def _compute_performance(self, holdings, cash):
        """
        Returns the current portfolio performance
        :return: value of current performance
        """
        return self._compute_expected_payoff(holdings, cash) \
               - self._get_risk_penalty() * self._compute_var_payoff(holdings)

    def _is_order_profitable(self, order: Order):
        """
        Returns true if accept the order can improve performance, false otherwise.
        :param order: an order
        :return: boolean
        """
        expected_stock_hold = self._get_stock_holding().copy()
        expected_cash = self._get_cash()

        # compute expected holding stocks and cash
        expected_stock_hold, expected_cash = _get_prospective_holdings(expected_stock_hold, expected_cash, order)

        # compute and compare performance
        return self._compute_performance(expected_stock_hold, expected_cash) \
               < self._compute_performance(self._get_stock_holding(), self._get_cash())

    def get_potential_performance(self, orders):
        """
        Returns the portfolio performance if the given list of orders is executed.
        The performance as per the following formula:
        Performance = ExpectedPayoff - b * PayoffVariance, where b is the penalty for risk.
        :param orders: list of orders
        :return: value of performance after executing all orders
        """
        prospect_stocks = self._get_stock_holding().copy()
        prospect_cash = self._get_cash()

        # iterate given order to get prospective holdings
        if type(orders) is Order:
            prospect_stocks, prospect_cash = _get_prospective_holdings(prospect_stocks, prospect_cash, orders)
        else:
            for i in orders:
                prospect_stocks, prospect_cash = _get_prospective_holdings(prospect_stocks, prospect_cash, i)

        return self._compute_performance(prospect_stocks, prospect_cash)

    def is_portfolio_optimal(self):
        """
        Returns true if the current holdings are optimal (as per performance formula and best price), false otherwise.
        :return: boolean
        """
        for stock, best_order in self._best_price.items():
            for order in best_order.values():
                if self.get_potential_performance(order) > \
                        self._compute_performance(self._get_stock_holding(), self._get_cash()):
                    return False

        return True

    def _find_optimal_portfolio(self):
        """
        Returns list of orders should be executed aim to optimise portfolio respect to the best price
        : return: list of order
        """
        order_list = []
        prospect_holdings = self._get_stock_holding().copy()
        prospect_cash = self._get_cash()

        try:
            for stock_id, best_price in self._best_price.items():
                for order in best_price.values():
                    if self.get_potential_performance(order) > \
                            self._compute_performance(prospect_holdings, prospect_cash):
                        # append in order list if can get higher performance
                        order_list.append(order)

                        # remove if cannot be executed after adding in order list
                        if self._is_valid_order(order_list):
                            prospect_holdings, prospect_cash = \
                                _get_prospective_holdings(prospect_holdings, prospect_cash, order)
                        else:
                            order_list.pop(-1)

            return order_list

        except IndexError:
            self.inform("method _find_optimal_portfolio raise error")

    def _place_order(self, market, orderSide: OrderSide, orderType: OrderType,
                     price: int, units: int, ref: str):
        """
        function for placing order
        :param market: stock market to place order
        :param orderType: order type to place, LIMIT or CANCEL
        :param orderSide: order side to place, BUY or SELL
        :param price: value to order price
        :param units: amount of ordering
        :param ref: reference in the order
        """
        new_order = Order.create_new(market)
        new_order.order_side = orderSide
        new_order.order_type = orderType
        new_order.price = price
        new_order.units = units
        new_order.ref = ref
        new_order.mine = True

        if self._is_valid_order([new_order]):
            super().send_order(new_order)
            self._waiting_for_order = False
            self._waiting_for_latest_holding = True

    def _respond_order(self, order: Order):
        """
        function for responding exist order
        :param order: order want to respond
        """
        new_order = copy.copy(order)
        if order.order_side == OrderSide.BUY:
            new_order.order_side = OrderSide.SELL
        else:
            new_order.order_side = OrderSide.BUY

        new_order.ref = self._order_ref_num()
        new_order.mine = True

        if self._is_valid_order([new_order]):
            super().send_order(new_order)
            self._waiting_for_order = False
            self._waiting_for_latest_holding = True

    def _cancel_order(self, order):
        """
        Cancel my order
        :param order: order pending in market
        """
        cancel_order = copy.copy(order)
        cancel_order.order_type = OrderType.CANCEL
        super().send_order(cancel_order)
        self._waiting_for_latest_holding = True

    def order_accepted(self, order):
        self.inform(f"order ref {order.ref} accept by server：{order}")
        if order.order_type == OrderType.LIMIT:
            self._sent_order[order.ref] = order
        self._check_pending_order()

    def order_rejected(self, info, order):
        self.warning(f"Order rejected {info}")

    def received_orders(self, orders: List[Order]):
        try:
            self._match_order_ref()
        except Exception:
            self.inform("match order error")

        try:
            self._cancel_pending_order()
        except BaseException:
            self.inform("_cancel_pending_order error")

        try:
            self._reset_best_price()
        except BaseException:
            self.inform("_reset_best_price error")

        try:
            for order_id, order in Order.current().items():
                self._renew_best_price(order)
        except:
            self.inform("renew price error")

        if not self.is_portfolio_optimal() and self._states_sync():
            # optimise portfolio, reactive
            try:
                order_to_respond = self._find_optimal_portfolio()

                # sending order
                if len(order_to_respond) != 0:
                    for i in order_to_respond:
                        self._respond_order(i)

            except IndexError:
                self.inform(f"reactive trade error")

        elif self._states_sync:
            # portfolio already optimal, proactive
            try:
                self._realise_note()
            except BaseException:
                self.inform(f"proactive trade error")

    def _realise_note(self):
        """
        Sell notes to realise cash when the bot have low cash
        """
        if self._get_cash() <= LOW_CASH_THRESHOLD \
                and self._get_stock_available()[Stock.NOTE.value] > 0 \
                and 'BUY' in self._best_price['Note'].keys():
            self._place_order(self.markets[self._market_ids['Note']], OrderSide.SELL, OrderType.LIMIT,
                              self._best_price['Note']['BUY'].price, MAX_ORDER_UNITS, self._order_ref_num())
            # self._respond_order(self._best_price['Note']['BUY'])
            self._waiting_for_order = False

    def _renew_best_price(self, order: Order):
        """
        renew the best bid and ask price in the market
        : param order: order received in market to renew the best price
        """
        try:
            if not order.mine and order.order_type == OrderType.LIMIT:
                if order.order_side.name not in self._best_price[order.market.item]:
                    self._best_price[order.market.item][order.order_side.name] = order
                else:
                    if order.price > self._best_price[order.market.item][order.order_side.name].price \
                            and order.order_side == OrderSide.BUY:
                        self._best_price[order.market.item][order.order_side.name] = order
                    elif order.price < self._best_price[order.market.item][order.order_side.name].price \
                            and order.order_side == OrderSide.SELL:
                        self._best_price[order.market.item][order.order_side.name] = order
        except (ValueError, TypeError):
            self.inform(f"Renew Best Price raise Error")

    def received_session_info(self, session: Session):
        if session.is_open:
            self.inform(f"Market is now open: {session.is_open}")
            self._market_open = True
        elif session.is_closed:
            self.inform(f"Market is now closed: {session.is_closed}")
            self._market_open = False
        elif session.is_paused:
            self.inform(f"Market is now closed: {session.is_paused}")
            self._market_open = False

    def pre_start_tasks(self):
        pass

    def _cancel_pending_order(self):
        """
        cancel pending order after sending for few seconds
        """
        if len(self._sent_order) > 0:
            try:
                for ref, order in self._sent_order.items():
                    if (datetime.datetime.now().time() >
                            (order.date_created + datetime.timedelta(seconds=ORDER_OVERDUE_SECOND)).time()):
                        self._cancel_order(order)
                        self._sent_order.pop(ref, f'order {ref} Already Cancel')

                    if len(self._sent_order) == 0:
                        break
                    else:
                        continue
            except IndexError:
                self.inform("Error in Cancel Order")

    def _check_pending_order(self):
        """
        set the bot stay in not waiting order states if still pending orders
        """
        if len(self._sent_order) > 0:
            self._waiting_for_order = False
        else:
            self._waiting_for_order = True

    def _match_order_ref(self):
        """
        match local dict of ref number and server my order to renew pending order
        """
        if len(self._sent_order) != 0 and len(Order.my_current()) > 0:
            try:
                exist_order = []
                for i in Order.my_current().values():
                    exist_order.append(i.ref)
                for i in self._sent_order.keys():
                    if i not in exist_order:
                        self._sent_order.pop(i, f'order {i} Already Cancel')
                    if len(self._sent_order) == 0:
                        break
            except BaseException:
                self.inform("_match_order_ref raise error")

    def _reset_best_price(self):
        try:
            for market_info in self.markets.values():
                security = market_info.item
                self._best_price[security] = {}
        except (IndexError, TypeError):
            self.inform("method _reset_best_price raise error")

    def _sync_assets_holdings(self):
        for _id, asset in self.holdings.assets.items():
            self._stock_holding[_get_stock_code(_id.item)] = asset.units
            self._stock_available[_get_stock_code(_id.item)] = asset.units_available
        self._waiting_for_latest_holding = False

    def received_holdings(self, holdings):
        holding_info = {'available_cash': holdings.cash_available}
        for _id, asset in holdings.assets.items():
            holding_info[asset.market.item] = asset.units_available

        self.inform(f"Current Asset:{holding_info}")
        self._sync_assets_holdings()
        self._check_pending_order()


if __name__ == "__main__":
    bot = CAPMBot(FM_ACCOUNT, FM_EMAIL, FM_PASSWORD, MARKETPLACE_ID)
    bot.run()
