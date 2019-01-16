import hashlib
from struct import unpack
import sys
import time


from . import (connector_wire_messages as cwm,
               AtLeastOnceSourceConnector,
               ProtocolError,
               ConnectorError)


if sys.version_info.major == 2:
    from base_meta2 import BaseMeta, abstractmethod
else:
    from base_meta3 import BaseMeta, abstractmethod


class BaseIter(BaseMeta):
    """
    A base class for creating iterator classes -- e.g. stateful iterators
    To use it, create your own subclass and implement the `__next__(self)`
    method.
    """
    def throw(self, type=None, value=None, traceback=None):
        raise StopIteration

    def __iter__(self):
        return self

    def next(self):
        return self.__next__()

    @abstractmethod
    def __next__(self):
        raise NotImplementedError


class BaseSource(BaseMeta):
    """
    All sources should inherit BaseSource and implement four methods:
        - `__str__(self)`: a human readable description of the source
        - `reset(self, pos=0)`: a mechanism to reset the source to a point of
          reference `pos`. `pos` is a positive integer, and may be transformed
          further within the method body.
        - `point_of_ref(self)`: the current position of the source.
          e.g. for a file source, this could be the position at the end of
          reading a sequence of bytes.
        - `__next__(self)`: return a tuple of the next value and the new
          point of reference.
    """
    @abstractmethod
    def __str__(self):
        """
        Return a human readable description of the source
        """
        raise NotImplementedError

    @abstractmethod
    def reset(self, pos=0):
        """
        Reset the source to position `pos`.
        `pos` is an integer point of reference. The source may do additional
        transformations in order to determine what internal position to reset
        to.
        """
        raise NotImplementedError

    @abstractmethod
    def point_of_ref(self):
        """
        Return the current point of reference
        """
        raise NotImplementedError

    @abstractmethod
    def __next__(self):
        """
        Return a tuple of the next message from the source and the point of
        reference after reading it.
        E.g. for a file source, it could be the bytes read, and the byte
        position after reading them.
        """
        raise NotImplementedError


class FramedFileReader(BaseIter, BaseSource):
    """
    A framed file reader iterator with a resettable position.

    Usage: `FramedFileReader(filename)`.
    Data should have U32 length headers followed by data bytes, followed by
    the next datum's length header and bytes, and so on until the end of the
    file.
    """
    def __init__(self, filename):
        self.file = open(filename, mode='rb')
        self.name = filename.encode()
        self.key = filename.encode()

    def __str__(self):
        return ("FramedFileReader(filename: {}, closed: {})"
                .format(self.name, self.file.closed))

    def point_of_ref(self):
        try:
            return self.file.tell()
        except:
            return -1

    def reset(self, pos=0):
        print("resetting {} to position {}".format(self.__str__(), pos))
        self.file.seek(pos)

    def __next__(self):
        # read header
        h = self.file.read(4)
        if not h:
            raise StopIteration
        h_bytes = unpack('>I', h)[0]
        b = self.file.read(h_bytes)
        if not b:
            raise StopIteration
        return (b, self.file.tell())

    def close(self):
        self.file.close()

    def __del__(self):
        try:
            self.close()
        except:
            pass


class MultiSourceConnector(AtLeastOnceSourceConnector, BaseIter):
    """
    MultiSourceConnector

    Send data from mutliple sources in a round-robin fashion using the
    AtLeastOnceSourceConnector protocol and superclass.
    New sources may be added at any point.

    An iterator interface is used to read and send the next datum to the
    Wallaroo source, for use with an external loop, such as
    ```
    client = MultiSourceConnector(
        "0.0.1", "monster", "celsius at least once", "instance",
        args=None,
        required_params=['host', 'port', 'filenames'])

    # Open a connection with a hello message
    client.connect()

    params = client.params
    filenames = params.filenames.split(',')


    # Open FramedFileReader
    for fn in filenames:
        client.add_source(FramedFileReader(filename = fn))

    # Rely on the iterator method of our connector subclass
    client.join()
    print("Reached the end of all files. Shutting down.")
    ```
    """
    def __init__(self, version, cookie, program_name, instance_name,
                 args=None, required_params=[], optional_params=[]):
        AtLeastOnceSourceConnector.__init__(self,
                                            version,
                                            cookie,
                                            program_name,
                                            instance_name,
                                            args, required_params,
                                            optional_params)
        self.sources = {} # stream_id: [source instance, acked point of ref]
        self.keys = []
        self._idx = -1
        self.joining = set()
        self.open = set()
        self.closed = set()
        self._added_source = False

    def add_source(self, source):
        self._added_source = True
        # add to self.sources
        _id = self.get_id(source.name)
        # check if we already have some ack data for this source
        _, acked = self.sources.get(_id, (None, None))
        if acked is not None:
            print("NH: resetting source from a priori ack")
            source.reset(acked)
        self.sources[_id] = [source, acked]
        self.keys.append(_id)
        # add to joining set so we can control the starting sequence
        self.joining.add(_id)
        # send a notify
        self.notify(_id, source.name, source.point_of_ref())

    def remove_source(self, source):
        _id = self.get_id(source.name)
        if _id in self.sources:
            # close and remove the source
            self.sources.pop(_id)
            self.keys.remove(_id)
            source.close()
            # add it to closed so we keep track of it
            self.closed.add(_id)

    @staticmethod
    def get_id(text):
        """
        Repeatable hash from text to 64-bit unsigned integer using a truncated
        SHA256.
        """
        h = hashlib.new('sha256')
        h.update(text)
        return int(h.hexdigest()[:16], 16)

    # Make this class an iterable:
    def __next__(self):
        if len(self.keys) > 0:
            try:
                # get next position
                self._idx = (self._idx + 1) % len(self.keys)
                # get key of that position
                key = self.keys[self._idx]
                # if stream is not in an open state, return nothing.
                if not key in self.open:
                    return None
                # get source at key
                source = self.sources[key][0]
                # get value from source
                value, point_of_ref = next(source)
                # send it as a message
                msg = cwm.Message(
                    stream_id = key,
                    flags = cwm.Message.Key,
                    message_id = point_of_ref,
                    key = source.key,
                    message = value)
                return msg
            except StopIteration:
                # if the source threw a StopIteration, send an EOS message
                # for it, then close it and remove it from sources
                self.closed.add(key)
                self.open.discard(key)
                source.close()
                del self.sources[key]
                self.keys.pop(self._idx)
                self._idx -= 1 # to avoid skipping in the round-robin sender
                self.end_of_stream(stream_id = key)
                return None
            except IndexError:
                # Index might have overflowed due to manual remove_source
                # will be corrected in the next iteration
                return None
        elif not self._added_source:
            # In very fast select loops, we might reach the end condition
            # before we have a chance to add our first source
            return None
        else:
            raise StopIteration

    def stream_added(self, stream):
        print("NH: stream_added({})".format(stream))
        source, acked = self.sources.get(stream.id, (None, None))
        if source:
            if stream.point_of_ref != source.point_of_ref():
                print("NH: updating point of ref")
                source.reset(stream.point_of_ref)

        # probably got this as part of the _handle_ok logic. Store the ack
        # and use when a source matching the stream id is added
        else:
            print("NH: unknown source id, storing ack por for later")
            self.sources[stream.id] = [None, stream.point_of_ref]

    def stream_removed(self, stream):
        print("NH: stream_removed({})".format(stream))

    def stream_opened(self, stream):
        print("NH: stream_opened({})".format(stream))
        source, acked = self.sources.get(stream.id, (None, None))
        if source:
            if stream.id in self.joining:
                print("NH: stream joined: {}".format(stream.id))
                self.joining.remove(stream.id)
                if stream.point_of_ref != source.point_of_ref():
                    print("NH: updating point of ref")
                    source.reset(stream.point_of_ref)
            self.open.add(stream.id)
        else:
            raise ConnectorError("Stream {} was opened for unknown source. "
                                 "Please use the add_source interface."
                                 .format(stream))

    def stream_closed(self, stream):
        print("NH: stream_closed({})".format(stream))
        source, acked = self.sources.get(stream.id, (None, None))
        if source:
            if stream.id in self.open:
                print("NH: Closing stream and moving to joining")
                # this source is waiting for a NotifyAck
                # move it to joining
                self.open.remove(stream.id)
                self.joining.add(stream.id)
            else: # source has been closed, so remove it entirely
                print("NH: closing source? {}".format(source))
                self.closed.add(stream.id)
                # trigger whatever is in source's __del__
                del source
        else:
            pass

    def stream_acked(self, stream):
        print("NH: stream_acked({})".format(stream))
        source, acked = self.sources.get(stream.id, (None, None))
        print("NH: source, acked : {}, {}".format(source, acked))
        if source:
            if acked:
                if stream.point_of_ref < acked:
                    print("WARNING: got an ack for older point of reference"
                          " for stream {}".format(stream))
                    source.reset(stream.point_of_ref)
            else:
                # source was added before connect()\handle_ok => reset
                source.reset(stream.point_of_ref)
            # update acked point of ref for the source
            self.sources[stream.id][1] = stream.point_of_ref
        elif stream.id in self.closed:
            pass
        else:
            raise ConnectorError("Stream {} was opened for unknown source. "
                                 "Please use the add_source interface."
                                 .format(stream))