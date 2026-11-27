from collections import deque
from dataclasses import dataclass
from datetime import date
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class _ExpiryNode:
    key: date
    value: object
    left: "_ExpiryNode | None" = None
    right: "_ExpiryNode | None" = None


class LeaseExpiryTree:
    """Binary search tree for ordered lease expiry lookup."""

    def __init__(self):
        self.root = None

    def insert(self, key: date, value: object):
        def add(node):
            if node is None:
                return _ExpiryNode(key, value)
            if key < node.key:
                node.left = add(node.left)
            else:
                node.right = add(node.right)
            return node

        self.root = add(self.root)

    def in_order(self):
        result = []

        def walk(node):
            if node:
                walk(node.left)
                result.append(node.value)
                walk(node.right)

        walk(self.root)
        return result


class RenewalQueue(Generic[T]):
    def __init__(self):
        self._items = deque()

    def enqueue(self, item: T):
        self._items.append(item)

    def dequeue(self):
        return self._items.popleft() if self._items else None

    def __iter__(self):
        return iter(self._items)


@dataclass
class _PaymentNode(Generic[T]):
    value: T
    previous: "_PaymentNode[T] | None" = None
    next: "_PaymentNode[T] | None" = None


class PaymentHistory(Generic[T]):
    def __init__(self):
        self.head = None
        self.tail = None

    def append(self, value: T):
        node = _PaymentNode(value, previous=self.tail)
        if self.tail:
            self.tail.next = node
        else:
            self.head = node
        self.tail = node

    def chronological(self):
        node = self.head
        while node:
            yield node.value
            node = node.next

    def newest_first(self):
        node = self.tail
        while node:
            yield node.value
            node = node.previous


class ResourceGraph:
    def __init__(self):
        self.adjacency = {}

    def connect(self, resource, shared_resource):
        self.adjacency.setdefault(resource, set()).add(shared_resource)
        self.adjacency.setdefault(shared_resource, set()).add(resource)


class UndoStack(Generic[T]):
    def __init__(self):
        self._items = []

    def push(self, action: T):
        self._items.append(action)

    def pop(self):
        return self._items.pop() if self._items else None
