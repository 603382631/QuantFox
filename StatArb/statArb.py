from pyalgotrade import strategy
from pyalgotrade.barfeed import yahoofeed
from pyalgotrade import plotter
from pyalgotrade.tools import yahoofinance
from pyalgotrade.stratanalyzer import returns
from pyalgotrade.stratanalyzer import sharpe
from pyalgotrade.utils import stats

import os
import csv

etf = 'xlb'
instruments = ['apd', 'dd', 'dow', 'ecl', 'fcx', 'ip', 'lyb', 'mon', 'ppg', 'px']
instFeed = ['xlb', 'apd', 'dd', 'dow', 'ecl', 'fcx', 'ip', 'lyb', 'mon', 'ppg', 'px']
instPrices = {i:[] for i in instruments}
instStock = {i:0 for i in instruments}
etfStock = {etf:0}
etfPrices = []

enterSpread = 0.05
exitSpread = 0.03

class MyStrategy(strategy.Strategy):
    def __init__(self, feed, etf):
        strategy.Strategy.__init__(self, feed)
        self.getBroker().setUseAdjustedValues(True)
        self.__etf = etf
        
    def inventory(self, symbol, qInst, qEtf):
        self.__symbol = symbol
        self.__qInst = qInst
        self.__qEtf = qEtf
        instStock[symbol] = qInst
        etfStock[etf] = qEtf
        
    
    def onBars(self, bars):
        writer = csv.writer(open('orders.csv', 'ab'), delimiter=',')
        for symbol in instruments:
            # define shares | get prices
            shares = self.getBroker().getShares(symbol)
            instPrice = bars[symbol].getAdjClose()
            etfPrice = bars[self.__etf].getAdjClose()
            # append prices to list
            instPrices[symbol].append(instPrice)
            etfPrices.append(etfPrice)
            # normalize price
            naInstPrice = instPrice / instPrices[symbol][0]
            naEtfPrice = etfPrice / etfPrices[0]
            # define notational, spread                            
            notional = shares * instPrice
            spread = naInstPrice - naEtfPrice
            
            # define trade rules
            if spread <= -enterSpread and notional < 1000000:
                if instStock[symbol] == 0:
                    qInst = 10000 / instPrice
                    qEtf = 10000 / etfPrice
                    self.order(symbol, qInst)
                    self.order(self.__etf, -qEtf)
                    self.inventory(symbol, qInst, etfStock[etf] - qEtf)
                    inst_to_enter = [str(bars[symbol].getDateTime()), symbol, round(spread, 4), 'Buy', str(round(qInst))]
                    etf_to_enter = [str(bars[etf].getDateTime()), etf, round(spread, 4), 'Sell', str(round(qEtf))]
                    writer.writerow(inst_to_enter)
                    writer.writerow(etf_to_enter)
                else:
                    pass
            elif spread >= -exitSpread and notional > 0:
                if instStock[symbol] > 0:
                    qInst = 10000 / instPrice
                    qEtf = 10000 / etfPrice
                    self.order(symbol, -(instStock[symbol]))
                    self.order(self.__etf, qEtf)
                    self.inventory(symbol, 0, (etfStock[etf] + qEtf))
                    inst_to_enter = [str(bars[symbol].getDateTime()), symbol, round(spread, 4), 'Sell', str(round(qInst, 2))]
                    etf_to_enter = [str(bars[etf].getDateTime()), etf, round(spread, 4), 'Buy', str(round(qEtf, 2))]
                    writer.writerow(inst_to_enter)
                    writer.writerow(etf_to_enter)
                else:
                    pass
            else:
                pass
 
def build_feed(instFeed, fromYear, toYear):
    feed = yahoofeed.Feed()

    for year in range(fromYear, toYear+1):
        for symbol in instFeed:
            fileName = "%s-%d.csv" % (symbol, year)
            if not os.path.exists(fileName):
                print "Downloading %s %d" % (symbol, year)
                csv = yahoofinance.get_daily_csv(symbol, year)
                f = open(fileName, "w")
                f.write(csv)
                f.close()
            feed.addBarsFromCSV(symbol, fileName)
    return feed




def main(plot):
    # Download the bars.
    feed = build_feed(instFeed, 2011, 2012)
    
    myStrategy = MyStrategy(feed, etf)

    if plot:
        plt = plotter.StrategyPlotter(myStrategy, True, True, True)
    
    # Attach returns and sharpe ratio analyzers.
    retAnalyzer = returns.Returns()
    myStrategy.attachAnalyzer(retAnalyzer)
    sharpeRatioAnalyzer = sharpe.SharpeRatio()
    myStrategy.attachAnalyzer(sharpeRatioAnalyzer)
    # run the strategy
    myStrategy.run()
    print "Final portfolio value: $%.2f" % myStrategy.getResult()
    print "Anual return: %.2f %%" % (retAnalyzer.getCumulativeReturns()[-1] * 100)
    print "Average daily return: %.2f %%" % (stats.mean(retAnalyzer.getReturns()) * 100)
    print "Std. dev. daily return: %.4f" % (stats.stddev(retAnalyzer.getReturns()))
    print "Sharpe ratio: %.2f" % (sharpeRatioAnalyzer.getSharpeRatio(0, 252))
    
    if plot:
        plt.plot()

if __name__ == "__main__":
    main(True)