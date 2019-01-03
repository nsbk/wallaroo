/*

Copyright 2018 The Wallaroo Authors.

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
 implied. See the License for the specific language governing
 permissions and limitations under the License.

*/

use "collections"
use "ponytest"
use "promises"
use "wallaroo/core/aggregations"
use "wallaroo/core/common"
use "wallaroo/core/state"
use "wallaroo/core/topology"
use "wallaroo_labs/time"


class iso _TestDropLateData is UnitTest
  fun name(): String => "windows/_TestDropLateData"

  fun apply(h: TestHelper) ? =>
    let range: U64 = Seconds(10)
    // Tumbling windows have the same slide as range
    let slide = range
    let delay: U64 = Seconds(10)
    let policy: U16 = LateDataPolicy.drop()
    let tw = RangeWindows[USize, USize, _Total]("key", _Sum, range, slide,
      delay, policy)

    var res: ((USize | Array[USize] val | None), U64) =
      (recover Array[USize] end, 0)

    res = tw(3, Seconds(80), Seconds(100))
    h.assert_eq[USize](_array(res._1)?.size(), 0)
    res = tw(5, Seconds(50), Seconds(101))
    h.assert_eq[USize](_array(res._1)?.size(), 1)
    h.assert_eq[USize](_array(res._1)?(0)?, 3)
    res = tw(7, Seconds(50), Seconds(102))
    h.assert_eq[USize](_array(res._1)?.size(), 0)
    res = tw(11, Seconds(50), Seconds(103))
    h.assert_eq[USize](_array(res._1)?.size(), 0)

    true

  fun _array(res: (USize | Array[USize] val | None)): Array[USize] val ? =>
    match res
    | let a: Array[USize] val => a
    else error end

class iso _TestFireLateData is UnitTest
  fun name(): String => "windows/_TestFireLateData"

  fun apply(h: TestHelper) ? =>
    let range: U64 = Seconds(10)
    // Tumbling windows have the same slide as range
    let slide = range
    let delay: U64 = Seconds(10)
    let policy: U16 = LateDataPolicy.fire_per_message()
    let tw = RangeWindows[USize, USize, _Total]("key", _Sum, range, slide,
      delay, policy)

    var res: ((USize | Array[USize] val | None), U64) =
      (recover Array[USize] end, 0)

    res = tw(3, Seconds(80), Seconds(100))
    h.assert_eq[USize](_array(res._1)?.size(), 0)
    res = tw(5, Seconds(50), Seconds(101))
    h.assert_eq[USize](_array(res._1)?.size(), 2)
    h.assert_eq[USize](_array(res._1)?(0)?, 3)
    h.assert_eq[USize](_array(res._1)?(1)?, 5)
    res = tw(7, Seconds(50), Seconds(102))
    h.assert_eq[USize](_array(res._1)?.size(), 1)
    h.assert_eq[USize](_array(res._1)?(0)?, 7)
    res = tw(11, Seconds(50), Seconds(103))
    h.assert_eq[USize](_array(res._1)?.size(), 1)
    h.assert_eq[USize](_array(res._1)?(0)?, 11)

    true

  fun _array(res: (USize | Array[USize] val | None)): Array[USize] val ? =>
    match res
    | let a: Array[USize] val => a
    else error end
