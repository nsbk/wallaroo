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

use "wallaroo/core/common"
use "wallaroo/core/invariant"
use "wallaroo_labs/collection_helpers"
use "wallaroo_labs/mort"


trait LocalTopologyInitializerPhase
  fun name(): String

  fun ref application_created(lti: LocalTopologyInitializer ref) =>
    _invalid_call()
    Fail()

  fun ref application_initialized(lti: LocalTopologyInitializer ref) =>
    _invalid_call()
    Fail()

  fun ref application_ready_to_work(lti: LocalTopologyInitializer ref) =>
    _invalid_call()
    Fail()

  fun _invalid_call() =>
    @printf[I32]("Invalid call on local topology initializer phase %s\n"
      .cstring(), name().cstring())

class _ApplicationStartingPhase is LocalTopologyInitializerPhase
  fun name(): String => "_ApplicationStartingPhase"

  fun ref application_created(lti: LocalTopologyInitializer ref) =>
    lti.application_created()

class _ApplicationCreatedPhase is LocalTopologyInitializerPhase
  fun name(): String => "_ApplicationCreatedPhase"

  fun ref application_initialized(lti: LocalTopologyInitializer ref) =>
    lti.application_initialized()

class _ApplicationInitializedPhase is LocalTopologyInitializerPhase
  fun name(): String => "_ApplicationInitializedPhase"

  fun ref application_ready_to_work(lti: LocalTopologyInitializer ref) =>
    lti.application_ready_to_work()

class _ApplicationReadyToWorkPhase is LocalTopologyInitializerPhase
  fun name(): String => "_ApplicationReadyToWorkPhase"

  fun ref application_ready_to_work(lti: LocalTopologyInitializer ref) =>
    None
