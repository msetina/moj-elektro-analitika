from collections.abc import Iterable
from datetime import date
from logging import Logger

import pandas as pd
from moj_elektro_v1 import MeterReadings

from moj_elektro_analitika.moj_elektro_readings_utils import (
    calc_poraba_over_slots,
)


class PorabaMojElektro(object):
    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self.__iter_data: Iterable | None = None
        self.__error: BaseException | None = None

    def get_error(self):
        return self.__error

    async def __call__(self, api_key: str, EIMM: str, frm_d: date, to_d: date):
        try:
            self.__error = None
            async with MeterReadings.get_session() as session:
                rdngs_lst = []
                async for rdngs in MeterReadings.generate_readings(
                    session,
                    api_key,
                    EIMM,
                    frm_d,
                    to_d,
                    ["A+", "P+"],
                    self._logger,
                ):
                    rdngs_lst.extend(rdngs)
                data_ld = pd.DataFrame(rdngs_lst)
                slot_list = ["Tarifa", "Blok"]
                return_vals = list()
                for slot_name in slot_list:
                    pt = calc_poraba_over_slots(data_ld, slot_name)
                    return_vals1 = pt.to_dict("records")
                    for i, ax in enumerate(
                        pt.axes[0].to_frame().to_dict("records")
                    ):
                        return_vals1[i].update(ax)
                    return_vals.extend(return_vals1)
                self.__iter_data = iter(return_vals)

        except Exception as e:
            self.__error = e
            self._logger.error(f"Prišlo je do napake: {e}")
            self.__iter_data = None
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.__iter_data is None:
            raise StopAsyncIteration()
        else:
            try:
                return next(self.__iter_data)
            except StopIteration:
                raise StopAsyncIteration()
