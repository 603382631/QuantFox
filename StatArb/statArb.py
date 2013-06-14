from pyalgotrade.stratanalyzer import returns, trades, drawdown, sharpe
from pyalgotrade.tools import yahoofinance
from pyalgotrade.barfeed import yahoofeed
from pyalgotrade.utils import stats
from pyalgotrade import strategy, plotter, dataseries
from datetime import datetime
import numpy as np
from numpy import mean, std
import os, csv
import statArbVars as v
from pyalgotrade.talibext import indicator
from pyalgotrade.technical import bollinger
import talib
from talib import MA_Type


startYear = v.startYear
endYear = v.endYear
lookBack = v.lookBack
start = startYear - lookBack
end = endYear - lookBack
etf = v.etf
instrument_list = v.instrument_list
orders_file = v.orders_file

instReader = csv.reader(open(instrument_list, "rb"), delimiter = ",")
instruments = [symbol for line in instReader for symbol in line]
print instruments

instFeed = [symbol for symbol in instruments]
instFeed.append(etf)

bbandPeriod = v.bbandPeriod
stopLoss = v.stopLoss
stop = v.stop
starting_cash = v.starting_cash

instPrices = {i:[] for i in instruments}
etfPrices = [] 
naInstPrices = {i:[] for i in instruments}                  # For plotting normalized price                                   
naEtfPrices = []                                            # For plotting normalized price
instSpread = {i:np.array([]) for i in instruments}          # For plotting spread and Bollingers
pltSpread = {i:[] for i in instruments}
instStock = {i:[0] for i in instruments}                    # [lastSpread]
etfStock = {i:[0] for i in instruments}                     # For correct order quantities
marketValue = {i:[0] for i in instruments}                  # Tracks cumulative gain
gain = {i:[0, 0] for i in instruments}                         # Tracks net gain
bollingerBands = {i:[[],[],[], []] for i in instruments}
tradeGain = {i:[0, 0, 0] for i in instruments}                 # [enteredSpread]
instMFI = {i:[] for i in instruments}                  # [[1-day],[MFR], [MFI]]
etfMFI = []                                            # [[1-day],[MFR], [MFI]]
spreadMFI = {i:np.array([]) for i in instruments}
#ltenMFI = {i:[] for i in instruments}
MFI_MACD = {i:[[],[],[],[], []] for i in instruments}              # [[MACD],[trigger],[oscillator], [ROC]]
plt_spread_MFI = {i:[] for i in instruments}



class MyStrategy(strategy.Strategy):
    def __init__(self, feed, etf, starting_cash):
        strategy.Strategy.__init__(self, feed)
        self.getBroker().setUseAdjustedValues(True)
        self.__etf = etf
        self._starting_Cash = starting_cash
        self.getBroker().setCash(starting_cash)
        
    def clearOrders(self, orders_file):
        orders_file = orders_file
        orders_file = open(orders_file, "w")
        orders_file.truncate()
        orders_file.close()
     
    def trade_life(self, symbol):
        self.__symbol = symbol
        if self.getBroker().getShares(symbol) != 0:
            tradeGain[symbol][2] += 1
        else:
            pass
        
    def orderWriter(self, year, month, day, symbol, etf, spread, instType, etfType, qInst, qEtf, gainLog):
        writer = csv.writer(open(orders_file, 'ab'), delimiter = ',')
        inst_to_enter = [str(year), str(month), str(day), symbol, round(spread, 4), instType, qInst, gainLog]
        etf_to_enter = [str(year), str(month), str(day), etf, round(spread, 4), etfType, qEtf, gainLog]
        writer.writerow(inst_to_enter)
        writer.writerow(etf_to_enter)
        
    def instValue(self, symbol, enterSpread, spread):
        self.__symbol = symbol
        self.__enterSpread = enterSpread
        self.__spread = spread
        
        if self.getBroker().getShares(symbol) > 0:
            gain = ((spread - enterSpread) / enterSpread)
        elif self.getBroker().getShares(symbol) < 0:
            gain = ((enterSpread - spread) / enterSpread)
        else:
            gain = 0
        return gain
 
    def tGain(self, symbol, spread):
        self.__symbol = symbol
        self.__spread = spread
        if self.getBroker().getShares(symbol) > 0:
            return (spread - tradeGain[symbol][1]) / tradeGain[symbol][1]
        elif self.getBroker().getShares(symbol) < 0:
            return  (tradeGain[symbol][1] - spread) / tradeGain[symbol][1]
        else:
            return 0
        
    def enterBuyInst(self, symbol, instPrice, etfPrice, spread, qInst, qEtf):
        self.__symbol = symbol
        self.__instPrice = instPrice
        self.__etfPrice = etfPrice
        self.__spread = spread
        self.enterLong(symbol, qInst, True)
        self.enterShort(self.__etf, qEtf, True)
        instStock[symbol] = spread
        etfStock[symbol] = -qEtf
        
    def exitBuyInst(self, symbol, instShares, instPrice, etfPrice, spread, qInst, qEtf):
        self.__symbol = symbol
        self.__instShares = instShares
        self.__instPrice = instPrice
        self.__etfPRice = etfPrice
        self.__spread = spread
        self.enterShort(symbol, qInst, True)
        self.enterLong(self.__etf, qEtf, True)
        instStock[symbol] = spread
        etfStock[symbol] = 0
        
    def exitShortInst(self, symbol, instShares, instPrice, etfPrice, spread, qInst, qEtf):
        self.__symbol = symbol
        self.__instShares = instShares
        self.__instPrice = instPrice
        self.__etfPrice = etfPrice
        self.__spread = spread
        self.enterLong(symbol, qInst, True)
        self.enterShort(self.__etf, qEtf, True)
        instStock[symbol] = spread
        etfStock[symbol] = 0
        
    def enterShortInst(self, symbol, instPrice, etfPrice, spread, qInst, qEtf):
        self.__symbol = symbol
        self.__instPrice = instPrice
        self.__etfPRice = etfPrice
        self.__spread = spread
        self.enterShort(symbol, qInst, True)
        self.enterLong(self.__etf, qEtf, True)
        instStock[symbol] = spread
        etfStock[symbol] = qEtf

    """def tenMFI(self, symbol):
        self.__symbol = symbol
        if len(spreadMFI[symbol]) >= 9:
            tenMFI = mean(spreadMFI[symbol][-9:])
        else:
            tenMFI = 0
        return tenMFI"""
        
    def bbands(self, symbol):
        spreadDS = instSpread[symbol]
        if len(etfPrices) >= bbandPeriod:
            upper = talib.BBANDS(spreadDS, bbandPeriod, 2, 2)[0][-1]
            middle = talib.BBANDS(spreadDS, bbandPeriod, 2, 2)[1][-1]
            lower = talib.BBANDS(spreadDS, bbandPeriod, 2, 2)[2][-1]
            #print "Lower :" + str(lower)
            #print "Middle: " + str(middle)
            #print "Upper: " + str(upper)
        else:
            #print "none"
            lower = 0
            middle = 0
            upper = 0
        bollingerBands[symbol][0].append(lower)
        bollingerBands[symbol][1].append(middle)
        bollingerBands[symbol][2].append(upper)
        return upper, middle, lower
    
    """def get_etf_MFI(self, etf):
        self.__etf = etf
        etf_barDs = self.getFeed().getDataSeries(etf)
        if len(etfPrices) >= 14:
            etf_MFI = indicator.MFI(etf_barDs, 252, 14)[-1]
        else:
            etf_MFI = 0
        etfMFI.append(etf_MFI)
        return etf_MFI
        
    def get_sym_MFI(self, symbol):
        self.__symbol = symbol
        sym_barDs = self.getFeed().getDataSeries(symbol)
        if len(etfPrices) >= 14:
            sym_MFI = indicator.MFI(sym_barDs, 252, 14)[-1]
        else:
            sym_MFI = 0
        instMFI[symbol].append(sym_MFI)
        return sym_MFI
    
    def get_spread_MFI(self, symbol):
        if len(etfPrices) > 14:
            etf_MFI = self.get_etf_MFI(etf)
            sym_MFI = self.get_sym_MFI(symbol)
            spread_MFI = (sym_MFI / etf_MFI)
        else:
            spread_MFI = 0
        spreadMFI[symbol] = np.append(spreadMFI[symbol], spread_MFI)
        plt_spread_MFI[symbol].append(spread_MFI)
        return spread_MFI"""
        
    def get_MFI_MACD(self, symbol): #, spread_MFI):
        self.__symbol = symbol
        spreadDS = instSpread[symbol]
        #self.__spread_MFI = spread_MFI
        if len(etfPrices) >= 35:
            #MACD = talib.MACD(spreadMFI[symbol], 12, 26, 9)[0][-1]
            #MACD_trigger = talib.MACD(spreadMFI[symbol], 12, 26, 9)[1][-1]
            #MACD_oscillator = talib.MACD(spreadMFI[symbol], 12, 26, 9)[2][-1]
            MACD = talib.MACD(spreadDS, 12, 26, 9)[0][-1]
            MACD_trigger = talib.MACD(spreadDS, 12, 26, 9)[1][-1]
            MACD_oscillator = talib.MACD(spreadDS, 12, 26, 9)[2][-1]
            #print "MACD: " + str(MACD)
            #print "MACD TRIP: " + str(MACD_trigger)
            #print "MACD OS: " + str(MACD_oscillator)
            
        else:
            MACD = 0
            MACD_trigger = 0
            MACD_oscillator = 0
        MFI_MACD[symbol][0].append(MACD)
        MFI_MACD[symbol][1].append(MACD_trigger)
        MFI_MACD[symbol][2].append(MACD_oscillator)
        #print MFI_MACD[symbol]
        return MACD, MACD_trigger, MACD_oscillator
    
    def get_MACD_ROC(self, symbol):
        self.__symbol = symbol
        if len(etfPrices) > 13:
            MACD_ROC = MFI_MACD[symbol][2][-1] - MFI_MACD[symbol][2][-13]
        else:
            MACD_ROC = 0
        MFI_MACD[symbol][3].append(MACD_ROC)
        return MACD_ROC
        """if len(etfPrices) > 4:
            MACD_ROC2 = MFI_MACD[symbol][3][-1] - MFI_MACD[symbol][3][-2]
        else:
            MACD_ROC2 = 0
        MFI_MACD[symbol][4].append(MACD_ROC2)
        return MACD_ROC2"""
        
        
    def onBars(self, bars):
        etfPrice = bars[self.__etf].getAdjClose()
        etfPrices.append(etfPrice)
    
        for symbol in instruments:
            #spread_MFI = self.get_spread_MFI(symbol)
            #print "spred MFI: " + str(spreadMFI[symbol])
            self.get_MFI_MACD(symbol) #, spread_MFI)
            MACD_ROC = self.get_MACD_ROC(symbol)
            
            
            
            # Get position status for symbol
            instShares = self.getBroker().getShares(symbol)
            # Get prices
            instPrice = bars[symbol].getAdjClose()
            # Append prices to list
            instPrices[symbol].append(instPrice)
            # Normalize pricespread
            #naInstPrice = instPrice / instPrices[symbol][0]
            #naInstPrices[symbol].append(naInstPrice)
            # Define Spread
            spread = instPrice / etfPrice
            #Update Market Value of Inventory
            instSpread[symbol] = np.append(instSpread[symbol], spread)                           # for plotting spread
            pltSpread[symbol].append(spread)
            gain = self.instValue(symbol, instStock[symbol], spread)
            tGain = self.tGain(symbol, spread)
            instStock[symbol] = spread                                  # track last spread
            marketValue[symbol].append(marketValue[symbol][-1] + gain)
            self.trade_life(symbol)
            trade_age = tradeGain[symbol][2]
            #print trade_age
                          
            

            #tenMFI = self.tenMFI(symbol)
            self.bbands(symbol)
            lower = bollingerBands[symbol][0][-1]
            middle = bollingerBands[symbol][1][-1]
            upper = bollingerBands[symbol][2][-1]
            print self.getBroker().getPositions()

            #ltenMFI[symbol].append(tenMFI)
            # Define trade rules
            if bars[symbol].getDateTime().year >= startYear:
                if stopLoss == True and ((tGain < stop) or (trade_age == 50)):
                    print "stop"
                    if instShares > 0:
                        qInst = instShares
                        qEtf = abs(etfStock[symbol])
                        instType = "SELL"
                        etfType = "Buy"
                        gainLog = round(tGain, 4) * 100
                        tradeGain[symbol][2] = 0
                        self.exitBuyInst(symbol, instShares, instPrice, etfPrice, spread, qInst, qEtf)
                        self.orderWriter(bars[symbol].getDateTime().year, bars[symbol].getDateTime().month, bars[symbol].getDateTime().day, symbol, etf, spread, instType, etfType, qInst, qEtf, gainLog)
                    elif instShares < 0:
                        qInst = abs(instShares)
                        qEtf = etfStock[symbol]
                        instType = "BUY"
                        etfType = "SELL"
                        gainLog = round(tGain, 4) * 100
                        tradeGain[symbol][2] = 0
                        self.exitShortInst(symbol, instShares, instPrice, etfPrice, spread, qInst, qEtf)
                        self.orderWriter(bars[symbol].getDateTime().year, bars[symbol].getDateTime().month, bars[symbol].getDateTime().day, symbol, etf, spread, instType, etfType, qInst, qEtf, gainLog)
                else:
                    if instShares == 0:
                        if spread >= lower and instSpread[symbol][-2] < bollingerBands[symbol][0][-2] and MACD_ROC > 0.00:     # Enter Long Inst
                            qInst = round((10000 / instPrice), 2)
                            qEtf = round((10000 / etfPrice), 2)
                            instType = "BUY"
                            etfType = "SELL"
                            gainLog = "N/A"
                            self.enterBuyInst(symbol, instPrice, etfPrice, spread, qInst, qEtf)
                            tradeGain[symbol][0] = 1
                            tradeGain[symbol][1] = spread
                            self.orderWriter(bars[symbol].getDateTime().year, bars[symbol].getDateTime().month, bars[symbol].getDateTime().day, symbol, etf, spread, instType, etfType, qInst, qEtf, gainLog)
                        elif spread <= upper and instSpread[symbol][-2] > bollingerBands[symbol][2][-2] and MACD_ROC < -0.00:   # Enter Short Inst
                            qInst = round((10000 / instPrice), 2)
                            qEtf = round((10000 / etfPrice), 2)
                            instType = "SELL"
                            etfType = "Buy"
                            tradeGain[symbol][0] = -1
                            tradeGain[symbol][1] = spread
                            gainLog = round(tGain, 4) * 100
                            self.enterShortInst(symbol, instPrice, etfPrice, spread, qInst, qEtf)
                            self.orderWriter(bars[symbol].getDateTime().year, bars[symbol].getDateTime().month, bars[symbol].getDateTime().day, symbol, etf, spread, instType, etfType, qInst, qEtf, gainLog)
                        else:
                            pass
                    elif instShares > 0:        # Exit Long Inst
                        if spread >= middle:
                            qInst = instShares
                            qEtf = abs(etfStock[symbol])
                            instType = "SELL"
                            etfType = "Buy"
                            gainLog = round(tGain, 4) * 100
                            tradeGain[symbol][2] = 0
                            self.exitBuyInst(symbol, instShares, instPrice, etfPrice, spread, qInst, qEtf)
                            self.orderWriter(bars[symbol].getDateTime().year, bars[symbol].getDateTime().month, bars[symbol].getDateTime().day, symbol, etf, spread, instType, etfType, qInst, qEtf, gainLog)
                        else:
                            pass
                    elif instShares < 0:        # Exit Short Inst
                        if spread <= middle:
                            qInst = abs(instShares)
                            qEtf = etfStock[symbol]
                            instType = "BUY"
                            etfType = "SELL"
                            gainLog = round(tGain, 4) * 100
                            tradeGain[symbol][2] = 0
                            self.exitShortInst(symbol, instShares, instPrice, etfPrice, spread, qInst, qEtf)
                            self.orderWriter(bars[symbol].getDateTime().year, bars[symbol].getDateTime().month, bars[symbol].getDateTime().day, symbol, etf, spread, instType, etfType, qInst, qEtf, gainLog)
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
    feed = build_feed(instFeed, start, endYear)
    # Define Strategy
    myStrategy = MyStrategy(feed, etf, starting_cash)
    # Attach returns and sharpe ratio analyzers.
    returnsAnalyzer = returns.Returns()
    myStrategy.attachAnalyzer(returnsAnalyzer)
    sharpeRatioAnalyzer = sharpe.SharpeRatio()
    myStrategy.attachAnalyzer(sharpeRatioAnalyzer)
    tradesAnalyzer = trades.Trades()
    myStrategy.attachAnalyzer(tradesAnalyzer)
    drawDownAnalyzer = drawdown.DrawDown()
    myStrategy.attachAnalyzer(drawDownAnalyzer)
    
    if plot:
        symbol = "BHI"
        #naInstPriceDS = dataseries.SequenceDataSeries(naInstPrices[symbol])
        #naEtfPriceDS = dataseries.SequenceDataSeries(naEtfPrices)
        spreadDS = dataseries.SequenceDataSeries(pltSpread[symbol])
        returnDS = dataseries.SequenceDataSeries(marketValue[symbol])
        instMFIds = dataseries.SequenceDataSeries(instMFI[symbol])
        etfMFIds = dataseries.SequenceDataSeries(etfMFI)
        MACD_ROC = dataseries.SequenceDataSeries(MFI_MACD[symbol][3])
        spreadMFIds = dataseries.SequenceDataSeries(spreadMFI[symbol])
        middleBandDS = dataseries.SequenceDataSeries(bollingerBands[symbol][1])
        upperBandDS = dataseries.SequenceDataSeries(bollingerBands[symbol][2])
        lowerBandDS = dataseries.SequenceDataSeries(bollingerBands[symbol][0])
        #tenMFI = dataseries.SequenceDataSeries(ltenMFI[symbol])
        MFI_MACD_ds = dataseries.SequenceDataSeries(MFI_MACD[symbol][0])
        MFI_MACDtrigger_ds = dataseries.SequenceDataSeries(MFI_MACD[symbol][1])
        MFI_MACDoscillator_ds = dataseries.SequenceDataSeries(MFI_MACD[symbol][2])
        plt = plotter.StrategyPlotter(myStrategy, False, False, False)
        plt.getOrCreateSubplot("spread").addDataSeries(symbol + ":" + etf, spreadDS)
        plt.getOrCreateSubplot("spread").addDataSeries("Middle", middleBandDS)
        plt.getOrCreateSubplot("spread").addDataSeries("Upper", upperBandDS)
        plt.getOrCreateSubplot("spread").addDataSeries("Lower", lowerBandDS)
        #plt.getOrCreateSubplot("MFI").addDataSeries("10 MFI", tenMFI)

        plt.getOrCreateSubplot("returns").addDataSeries(symbol + "-Return", returnDS)
        plt.getOrCreateSubplot("returns").addDataSeries("Cum. return", returnsAnalyzer.getCumulativeReturns())
        #plt.getOrCreateSubplot("MFI").addDataSeries("MFI-MACD", MFI_MACD_ds)
        #plt.getOrCreateSubplot("MFI").addDataSeries("Trigger", MFI_MACDtrigger_ds)
        #plt.getOrCreateSubplot("MFI").addDataSeries("Oscillator", MFI_MACDoscillator_ds)
        plt.getOrCreateSubplot("MFI").addDataSeries("ROC", MACD_ROC)
        #plt.getOrCreateSubplot("MFI").addDataSeries(symbol + "-MFI", instMFIds)
        #plt.getOrCreateSubplot("MFI").addDataSeries(etf + "-MFI", etfMFIds)
        #plt.getOrCreateSubplot("MFI").addDataSeries("80", 80)
        #plt.getOrCreateSubplot("MFI").addDataSeries("20", 20)
        
        
    
    # Run the strategy
    print "Running Strategy..."
    myStrategy.clearOrders(orders_file)
    myStrategy.run()
    
    print "Final portfolio value: $%.2f" % myStrategy.getResult()
    print "Anual return: %.2f %%" % (returnsAnalyzer.getCumulativeReturns()[-1] * 100)
    print "Average daily return: %.2f %%" % (stats.mean(returnsAnalyzer.getReturns()) * 100)
    print "Std. dev. daily return: %.4f" % (stats.stddev(returnsAnalyzer.getReturns()))
    print "Sharpe ratio: %.2f" % (sharpeRatioAnalyzer.getSharpeRatio(0, 252))
    print
    print "Total trades: %d" % (tradesAnalyzer.getCount())
    if tradesAnalyzer.getCount() > 0:
        profits = tradesAnalyzer.getAll()
        print "Avg. profit: $%2.f" % (profits.mean())
        print "Profits std. dev.: $%2.f" % (profits.std())
        print "Max. profit: $%2.f" % (profits.max())
        print "Min. profit: $%2.f" % (profits.min())
        returnz = tradesAnalyzer.getAllReturns()
        print "Avg. return: %2.f %%" % (returnz.mean() * 100)
        print "Returns std. dev.: %2.f %%" % (returnz.std() * 100)
        print "Max. return: %2.f %%" % (returnz.max() * 100)
        print "Min. return: %2.f %%" % (returnz.min() * 100)
    print
    print "Profitable trades: %d" % (tradesAnalyzer.getProfitableCount())
    if tradesAnalyzer.getProfitableCount() > 0:
        profits = tradesAnalyzer.getProfits()
        print "Avg. profit: $%2.f" % (profits.mean())
        print "Profits std. dev.: $%2.f" % (profits.std())
        print "Max. profit: $%2.f" % (profits.max())
        print "Min. profit: $%2.f" % (profits.min())
        returnz = tradesAnalyzer.getPositiveReturns()
        print "Avg. return: %2.f %%" % (returnz.mean() * 100)
        print "Returns std. dev.: %2.f %%" % (returnz.std() * 100)
        print "Max. return: %2.f %%" % (returnz.max() * 100)
        print "Min. return: %2.f %%" % (returnz.min() * 100)
    print
    print "Unprofitable trades: %d" % (tradesAnalyzer.getUnprofitableCount())
    if tradesAnalyzer.getUnprofitableCount() > 0:
        losses = tradesAnalyzer.getLosses()
        print "Avg. loss: $%2.f" % (losses.mean())
        print "Losses std. dev.: $%2.f" % (losses.std())
        print "Max. loss: $%2.f" % (losses.min())
        print "Min. loss: $%2.f" % (losses.max())
        returnz = tradesAnalyzer.getNegativeReturns()
        print "Avg. return: %2.f %%" % (returnz.mean() * 100)
        print "Returns std. dev.: %2.f %%" % (returnz.std() * 100)
        print "Max. return: %2.f %%" % (returnz.max() * 100)
        print "Min. return: %2.f %%" % (returnz.min() * 100)
    print
    for symbol in instruments:
        print str(symbol)+ ": " + str(round(marketValue[symbol][-1], 4) * 100) + "%"
       
    if plot:
            plt.plot(datetime.strptime('01/01/' + str(startYear), '%m/%d/%Y'))

if __name__ == "__main__":
    main(True)
    
