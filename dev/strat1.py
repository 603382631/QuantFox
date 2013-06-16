import itertools
from pyalgotrade import strategy
from pyalgotrade.technical import ma
from pyalgotrade.technical import rsi

fromYear = 2009
toYear = 2011
sym_list = ["WFC", "DIS", "HSY", "COP"]
optimize = False

def parameters_generator():
    if optimize == True:
        entrySMA = range(150, 160)
        exitSMA = range(5, 6)
        rsiPeriod = range(2, 4)
        overBoughtThreshold = range(75, 80)
        overSoldThreshold = range(5, 10)
    else:
        entrySMA = range(150, 151)
        exitSMA = range(5, 6)
        rsiPeriod = range(2, 3)
        overBoughtThreshold = range(75, 76)
        overSoldThreshold = range(5, 6)
    return itertools.product(entrySMA, exitSMA, rsiPeriod, overBoughtThreshold, overSoldThreshold)
        
class MyStrategy(strategy.Strategy):
    def __init__(self, feed, entrySMA, exitSMA, rsiPeriod, overBoughtThreshold, overSoldThreshold):
        strategy.Strategy.__init__(self, feed, 2000)
        ds = feed["COP"].getCloseDataSeries()
        self.__entrySMA = ma.SMA(ds, entrySMA)
        self.__exitSMA = ma.SMA(ds, exitSMA)
        self.__rsi = rsi.RSI(ds, rsiPeriod)
        self.__overBoughtThreshold = overBoughtThreshold
        self.__overSoldThreshold = overSoldThreshold
        self.__longPos = None
        self.__shortPos = None

    def onEnterOk(self, position):
        pass

    def onEnterCanceled(self, position):
        if self.__longPos == position:
            self.__longPos = None
        elif self.__shortPos == position:
            self.__shortPos = None
        else:
            assert(False)

    def onExitOk(self, position):
        if self.__longPos == position:
            self.__longPos = None
        elif self.__shortPos == position:
            self.__shortPos = None
        else:
            assert(False)

    def onExitCanceled(self, position):
        # If the exit was canceled, re-submit it.
        self.exitPosition(position)

    def onBars(self, bars):
        # Wait for enough bars to be available to calculate SMA and RSI.
        if self.__exitSMA[-1] is None or self.__entrySMA[-1] is None or self.__rsi[-1] is None:
            return

        bar = bars["COP"]
        if self.__longPos != None:
            if self.exitLongSignal(bar):
                self.exitPosition(self.__longPos)
        elif self.__shortPos != None:
            if self.exitShortSignal(bar):
                self.exitPosition(self.__shortPos)
        else:
            if self.enterLongSignal(bar):
                self.__longPos = self.enterLong("COP", 10, True)
            elif self.enterShortSignal(bar):
                self.__shortPos = self.enterShort("COP", 10, True)

    def enterLongSignal(self, bar):
        return bar.getClose() > self.__entrySMA[-1] and self.__rsi[-1] <= self.__overSoldThreshold

    def exitLongSignal(self, bar):
        return bar.getClose() > self.__exitSMA[-1]

    def enterShortSignal(self, bar):
        return bar.getClose() < self.__entrySMA[-1] and self.__rsi[-1] >= self.__overBoughtThreshold

    def exitShortSignal(self, bar):
        return bar.getClose() < self.__exitSMA[-1]
