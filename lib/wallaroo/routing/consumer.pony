trait tag Consumer
  be register_producer(producer: Producer)
  be unregister_producer(producer: Producer)

type CreditFlowProducerConsumer is (Producer & Consumer)
