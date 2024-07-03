from collections.abc import Iterable
from datetime import date
from logging import Logger

import pandas as pd
from moj_elektro_v1 import MeterReadings

from moj_elektro_analitika.moj_elektro_readings_utils import (
    calc_poraba_over_buckets,
)


class BucketsPorabaMojElektro(object):
    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self.__iter_data: Iterable | None = None

    async def __call__(
        self,
        api_key: str,
        EIMM: str,
        frm_d: date,
        to_d: date,
        buckets: int | list[float],
    ):
        try:
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
                pt = calc_poraba_over_buckets(data_ld, "P+", buckets)
                return_vals = pt.to_dict("records")
                for i, ax in enumerate(
                    pt.axes[0].to_frame().to_dict("records")
                ):
                    return_vals[i].update(ax)
                self.__iter_data = iter(return_vals)

        except Exception as e:
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
