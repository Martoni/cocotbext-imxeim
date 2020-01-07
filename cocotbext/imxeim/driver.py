#! /usr/bin/python3
# -*- coding: utf-8 -*-
#-----------------------------------------------------------------------------
# Author:   Fabien Marteau <fabien.marteau@armadeus.com>
# Created:  07/01/2020
#-----------------------------------------------------------------------------
#  Copyright (2020)  Armadeus Systems
#-----------------------------------------------------------------------------
""" driver
"""


import cocotb
from cocotb.decorators import coroutine
from cocotb.triggers import RisingEdge, Event
from cocotb.drivers import BusDriver
from cocotb.result import ReturnValue, TestFailure
from cocotb.binary import BinaryValue
from cocotb.decorators import public


def is_sequence(arg):
    return (not hasattr(arg, "strip") and
    hasattr(arg, "__getitem__") or
    hasattr(arg, "__iter__"))

class EIMAux():
    """
    EIM Auxiliary Wrapper Class

    wrap meta informations on bus transaction (internal only)
    """
    def __init__(self, sel=None, adr=0, datwr=None, waitStall=0, waitIdle=0, tsStb=0):
        self.sel        = sel
        self.adr        = adr
        self.datwr      = datwr
        self.waitIdle   = waitIdle
        self.waitStall  = waitStall
        self.ts         = tsStb


@public
class EIMOp():
    """
    EIM Operations Wrapper Class

    an attempt to wrap em tidy

    Args:
        adr: address of the operation
        dat: data to write, None indicates a read cycle
        idle: number of clock cycles between asserting cyc and stb
        sel: the selection mask for the operation
        acktimeout: number of clock cycles before asserting ack
    """
    def __init__(self, adr=0, dat=None, idle=0, sel=None, acktimeout=4):
        self.adr    = adr
        self.dat    = dat
        self.sel    = sel
        self.idle   = idle
        self.acktimeout = acktimeout

@public
class EIMRes():
    """
    EIM Result Wrapper Class.

    What's happend on the bus plus meta information on timing
    """

    def __init__(self, ack=0, sel=None, adr=0, datrd=None, datwr=None, waitIdle=0, waitStall=0, waitAck=0):
        self.ack        = ack
        self.sel        = sel
        self.adr        = adr
        self.datrd      = datrd
        self.datwr      = datwr
        self.waitStall  = waitStall
        self.waitAck    = waitAck
        self.waitIdle   = waitIdle


# TODO: Use of pipelined operations
class EIM(BusDriver):
    """
    EIM
    """

    _signals = ["dain", "daout", "daen", "lba", "rw", "cs"]
    _optional_signals = ["eb", "oe"]


    def __init__(self, entity, name, clock, width=32, signals_dict=None, **kwargs):
        if signals_dict is not None:
            self._signals=signals_dict
        BusDriver.__init__(self, entity, name, clock, **kwargs)
        # Drive some sensible defaults (setimmediatevalue to avoid x asserts)
        self._width = width
        self.bus.dain.setimmediatevalue(0)
        self.bus.lba.setimmediatevalue(1)
        self.bus.rw.setimmediatevalue(0)
        self.bus.cs.setimmediatevalue(1)


class EIMMaster(EIM):
    """
    EIM master
    """
    def __init__(self, entity, name, clock, timeout=None, width=16, **kwargs):
        sTo = ", no cycle timeout"
        if timeout is not None:
            sTo = ", cycle timeout is %u clockcycles" % timeout
        self.busy_event         = Event("%s_busy" % name)
        self._timeout           = timeout
        self.busy               = False
        self._acked_ops         = 0
        self._res_buf           = []
        self._aux_buf           = []
        self._op_cnt            = 0
        self._clk_cycle_count   = 0
        EIM.__init__(self, entity, name, clock, width, **kwargs)
        self.log.info("EIM Master created%s" % sTo)


    @coroutine 
    def _clk_cycle_counter(self):
        """
        Cycle counter to time bus operations
        """
        clkedge = RisingEdge(self.clock)
        self._clk_cycle_count = 0
        while self.busy:
            yield clkedge
            self._clk_cycle_count += 1


    @coroutine
    def _open_cycle(self):
        #Open new eim cycle
        if self.busy:
            self.log.error("Opening Cycle, but EIM Driver is already busy. Someting's wrong")
            yield self.busy_event.wait()
        self.busy_event.clear()
        self.busy       = True
        cocotb.fork(self._read())
        cocotb.fork(self._clk_cycle_counter()) 
        #self.bus.cyc    <= 1
        self.bus.lba <= 0
        self._acked_ops = 0  
        self._res_buf   = [] 
        self._aux_buf   = []
        self.log.debug("Opening cycle, %u Ops" % self._op_cnt)


    @coroutine
    def _close_cycle(self):
        #Close current eim cycle  
        clkedge = RisingEdge(self.clock)
        count           = 0
        last_acked_ops  = 0
        #Wait for all Operations being acknowledged by the slave before lowering the cycle line
        #This is not mandatory by the bus standard, but a crossbar might send acks to the wrong master
        #if we don't wait. We don't want to risk that, it could hang the bus
        while self._acked_ops < self._op_cnt:
            if last_acked_ops != self._acked_ops:
                self.log.debug("Waiting for missing acks: %u/%u" % (self._acked_ops, self._op_cnt) )
            last_acked_ops = self._acked_ops    
            #check for timeout when finishing the cycle            
            count += 1
            if (not (self._timeout is None)):
                if (count > self._timeout): 
                    raise TestFailure("Timeout of %u clock cycles reached when waiting for reply from slave" % self._timeout)                
            yield clkedge

        self.busy = False
        self.busy_event.set()
        self.bus.cs <= 1
        self.log.debug("Closing cycle")
        yield clkedge


    @coroutine 
    def _read(self):
        """
        Reader for slave replies
        """
        count = 0
        clkedge = RisingEdge(self.clock)
        while self.busy:
            if count >= 4: # XXX parametrize
                datrd = self.bus.daout.value
                #append reply and meta info to result buffer
                tmpRes =  EIMRes(sel=None, adr=None, datrd=datrd, datwr=None, waitIdle=None, waitStall=None, waitAck=self._clk_cycle_count)               
                self._res_buf.append(tmpRes)
                self._acked_ops += 1
            yield clkedge
            count += 1

    @coroutine
    def _drive(self, we, adr, datwr, sel, idle):
        """
        Drive the EIM Master Out Lines
        """

        clkedge = RisingEdge(self.clock)
        if self.busy:
            # insert requested idle cycles
            if idle is not None:
                idlecnt = idle
                while idlecnt > 0:
                    idlecnt -= 1
                    yield clkedge
            # set address
            self.bus.lba <= 0
            self.bus.dain <= adr
            yield clkedge
            self.bus.lba <= 1
            # drive outputs   
            self.bus.cs  <= 0
            self.bus.dain <= datwr
            self.bus.rw   <= we
            yield clkedge
            #append operation and meta info to auxiliary buffer
            self._aux_buf.append(EIMAux(sel, adr, datwr, idle, self._clk_cycle_count))
#XXX            yield self._wait_ack()
            self.bus.rw <= 0
        else:
            self.log.error("Cannot drive the EIM bus outside a cycle!")



    @coroutine
    def send_cycle(self, arg):
        """
        The main sending routine

        Args:
            list(EIMOperations)
        """
        cnt = 0
        clkedge = RisingEdge(self.clock)
        yield clkedge
        if is_sequence(arg):
            self._op_cnt = len(arg)
            if self._op_cnt < 1:
                self.log.error("List contains no operations to carry out")
            else:
                result = []
                yield self._open_cycle()

                for op in arg:
                    if not isinstance(op, EIMOp):
                        raise TestFailure("Sorry, argument must be a list of EIMOp (EIM Operation) objects!")    

                    self._acktimeout = op.acktimeout

                    if op.dat is not None:
                        we  = 1
                        dat = op.dat
                    else:
                        we  = 0
                        dat = 0
                    yield self._drive(we, op.adr, dat, op.sel, op.idle)
                    if op.sel is not None:
                        self.log.debug("#%3u WE: %s ADR: 0x%08x DAT: 0x%08x SEL: 0x%1x IDLE: %3u" % (cnt, we, op.adr, dat, op.sel, op.idle))
                    else:
                        self.log.debug("#%3u WE: %s ADR: 0x%08x DAT: 0x%08x SEL: None  IDLE: %3u" % (cnt, we, op.adr, dat, op.idle))
                    cnt += 1

                yield self._close_cycle()

                #do pick and mix from result- and auxiliary buffer so we get all operation and meta info
                for res, aux in zip(self._res_buf, self._aux_buf):
                    res.datwr       = aux.datwr
                    res.sel         = aux.sel
                    res.adr         = aux.adr
                    res.waitIdle    = aux.waitIdle
                    res.waitStall   = aux.waitStall
                    res.waitAck    -= aux.ts
                    result.append(res)

            raise ReturnValue(result)
        else:
            raise TestFailure("Sorry, argument must be a list of EIMOp (EIM Operation) objects!")
            raise ReturnValue(None)


