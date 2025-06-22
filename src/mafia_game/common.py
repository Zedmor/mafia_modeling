from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Type, TypeVar

import numpy as np

MAX_TURNS = 10
MAX_PLAYERS = 10
ARRAY_SIZE = 715


class Role(Enum):
    CITIZEN = 0
    SHERIFF = 1
    MAFIA = 2
    DON = 3
    UNKNOWN = 4


class Team(Enum):
    UNKNOWN = 0
    BLACK_TEAM = 1
    RED_TEAM = 2


class SerializeMixin:
    def serialize(self):
        serialized_data = []
        for field in fields(self):
            # Skip agent and log fields as they're not part of persistent game state data
            if field.name in ('agent', 'log'):
                continue
                
            field_value = getattr(self, field.name)
            if hasattr(field_value, "serialize"):
                serialized_data.append(field_value.serialize())
            elif isinstance(field_value, np.ndarray) or isinstance(field_value, list):
                serialized_data.append(field_value)
            elif isinstance(field_value, Enum):
                serialized_data.append([field_value.value])
            elif isinstance(field_value, int):
                serialized_data.append([field_value])
            else:
                raise TypeError(
                    f"Cannot serialize field '{field.name}' of type {type(field_value)}"
                )
        return np.concatenate(serialized_data)


T = TypeVar("T", bound="DeserializeMixin")


class DeserializeMixin:
    @classmethod
    def expected_size(cls):
        sum_of_all_sizes = 0
        for field in fields(cls):
            # Skip agent and log fields as they're not part of persistent game state data
            if field.name in ('agent', 'log'):
                continue
                
            field_type = field.type
            if hasattr(field_type, "expected_size"):
                sum_of_all_sizes += field_type.expected_size()
            elif field_type == np.ndarray or field_type == np.array:
                sum_of_all_sizes += field.metadata.get("size", 1)
            elif hasattr(field_type, '__origin__') or (isinstance(field_type, type) and issubclass(field_type, Enum)) or field_type == int:
                sum_of_all_sizes += 1
            else:
                raise TypeError(f"Unsupported field type: {field_type}")
        return sum_of_all_sizes

    @classmethod
    def deserialize(cls: Type[T], serialized_data: np.ndarray) -> T:
        deserialized_data = {}
        idx = 0

        for field in fields(cls):
            # Skip agent and log fields as they're not part of persistent game state data
            if field.name in ('agent', 'log'):
                continue
                
            field_type = field.type
            if field_type == int:
                # Deserialize integers
                field_value = int(serialized_data[idx])
                idx += 1
            elif field_type == np.ndarray or field_type == np.array:
                # Deserialize numpy arrays
                field_size = field.metadata.get(
                    "size", 1
                )  # Use metadata to specify size if needed
                field_value = serialized_data[idx : idx + field_size]
                idx += field_size
            elif hasattr(field_type, "deserialize_with_index"):
                # Recursively deserialize fields that are also DeserializeMixin
                field_value, idx = field_type.deserialize_with_index(
                    serialized_data, idx
                )
            elif isinstance(field_type, type) and issubclass(field_type, Enum):
                # Deserialize Enums
                field_value = field_type(serialized_data[idx])
                idx += 1
            else:
                raise TypeError(f"Unsupported field type: {field_type}")

            deserialized_data[field.name] = field_value

        return cls(**deserialized_data)

    @classmethod
    def deserialize_with_index(
        cls: Type[T], serialized_data: np.ndarray, start_idx: int
    ) -> (T, int):
        instance = cls.deserialize(
            serialized_data[start_idx : start_idx + cls.expected_size()]
        )
        return instance, start_idx + cls.expected_size()


class Check(SerializeMixin, DeserializeMixin):
    def __init__(self):
        self.checks = np.zeros(MAX_PLAYERS)

    def __setitem__(self, key, value):
        self.checks[key] = value

    def __getitem__(self, item):
        return self.checks[item]

    @classmethod
    def expected_size(cls):
        return MAX_PLAYERS

    def serialize(self):
        return self.checks

    @classmethod
    def deserialize(cls: Type[T], serialized_data: np.ndarray) -> T:
        check = cls()
        check.checks = serialized_data
        return check

    def __repr__(self):
        return f"{self.__class__.__name__}({[Team(v) for v in self.serialize()]})"


class Booleans(SerializeMixin, DeserializeMixin):
    def __init__(self):
        self.values = np.zeros(MAX_PLAYERS)

    def __setitem__(self, key, value):
        self.values[key] = value

    def __getitem__(self, item):
        return self.values[item]

    def serialize(self):
        return self.values

    def deserialize(serialized_booleans: np.ndarray):
        if serialized_booleans.size != MAX_TURNS:
            raise ValueError(
                "Serialized booleans must have a size of {}".format(MAX_TURNS)
            )

        booleans = Booleans()
        booleans.values = serialized_booleans
        return booleans

    @classmethod
    def expected_size(cls):
        return MAX_PLAYERS


@dataclass
class Checks(SerializeMixin, DeserializeMixin):
    checks: np.array = field(
        default_factory=lambda: np.array(
            [Check() for _ in range(MAX_TURNS)], dtype=object
        )
    )

    def __repr__(self):
        return f"{self.__class__.__name__}({self.serialize()})"

    def __post_init__(self):
        self._next_index = 0

    def add_check(self, check: Check):
        if not isinstance(check, Check):
            raise ValueError("Only Check instances can be added")
        if self._next_index >= len(self.checks):
            raise ValueError("All slots are occupied")
        self.checks[self._next_index] = check
        self._next_index += 1

    def serialize(self):
        return np.concatenate([c.serialize() for c in self.checks])

    @classmethod
    def deserialize(cls: Type[T], serialized_data: np.ndarray) -> T:
        check_length = MAX_PLAYERS
        num_checks = len(serialized_data) // check_length
        checks = []

        for i in range(num_checks):
            # Extract the serialized data for a single check
            check_data = serialized_data[i * check_length : (i + 1) * check_length]
            # Assuming Check has a deserialize method that accepts a NumPy array
            check = Check.deserialize(check_data)
            checks.append(check)

        return cls(checks=checks)

    @classmethod
    def expected_size(cls):
        return MAX_PLAYERS * MAX_TURNS


class Beliefs(Checks):

    def __repr__(self):
        return f"{self.__class__.__name__}({[Team(v) for v in self.serialize()]})"


class Votes(Checks):
    pass


class Kills(Checks):
    pass


class Nominations(Checks):
    pass
