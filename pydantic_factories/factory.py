import os
from abc import ABC
from collections import Counter, deque
from dataclasses import is_dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import EnumMeta
from inspect import isclass
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    ItemsView,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
)
from uuid import NAMESPACE_DNS, UUID, uuid1, uuid3, uuid4, uuid5

from faker import Faker
from pydantic import (
    UUID1,
    UUID3,
    UUID4,
    UUID5,
    AmqpDsn,
    AnyHttpUrl,
    AnyUrl,
    BaseModel,
    ByteSize,
    ConstrainedBytes,
    ConstrainedDecimal,
    ConstrainedFloat,
    ConstrainedInt,
    ConstrainedList,
    ConstrainedSet,
    ConstrainedStr,
    DirectoryPath,
    EmailStr,
    FilePath,
    FutureDate,
    HttpUrl,
    IPvAnyAddress,
    IPvAnyInterface,
    IPvAnyNetwork,
    Json,
    KafkaDsn,
    NameEmail,
    NegativeFloat,
    NegativeInt,
    NonNegativeInt,
    NonPositiveFloat,
    PastDate,
    PaymentCardNumber,
    PositiveFloat,
    PositiveInt,
    PostgresDsn,
    PyObject,
    RedisDsn,
    SecretBytes,
    SecretStr,
    StrictBool,
    StrictBytes,
    StrictFloat,
    StrictInt,
    StrictStr,
)
from pydantic.color import Color
from pydantic.fields import ModelField
from typing_extensions import Type, get_args

from pydantic_factories.constraints.constrained_collection_handler import (
    handle_constrained_collection,
)
from pydantic_factories.constraints.constrained_decimal_handler import (
    handle_constrained_decimal,
)
from pydantic_factories.constraints.constrained_float_handler import (
    handle_constrained_float,
)
from pydantic_factories.constraints.constrained_integer_handler import (
    handle_constrained_int,
)
from pydantic_factories.constraints.strings import (
    handle_constrained_bytes,
    handle_constrained_string,
)
from pydantic_factories.exceptions import (
    ConfigurationError,
    MissingBuildKwargError,
    ParameterError,
)
from pydantic_factories.fields import Ignore, Require
from pydantic_factories.protocols import (
    AsyncPersistenceProtocol,
    DataclassProtocol,
    SyncPersistenceProtocol,
)
from pydantic_factories.utils import (
    create_model_from_dataclass,
    is_literal,
    is_optional,
    is_pydantic_model,
    random,
)
from pydantic_factories.value_generators.complex_types import handle_complex_type
from pydantic_factories.value_generators.primitives import (
    create_random_boolean,
    create_random_bytes,
)

T = TypeVar("T", BaseModel, DataclassProtocol)

default_faker = Faker()


class ModelFactory(ABC, Generic[T]):
    __model__: Type[T]
    __faker__: Optional[Faker]
    __sync_persistence__: Optional[Union[Type[SyncPersistenceProtocol[T]], SyncPersistenceProtocol[T]]] = None
    __async_persistence__: Optional[Union[Type[AsyncPersistenceProtocol[T]], AsyncPersistenceProtocol[T]]] = None
    __allow_none_optionals__: bool = True

    @classmethod
    def seed_random(cls, seed: int) -> None:
        """
        Seeds Fake and random methods with seed
        """
        random.seed(seed)
        Faker.seed(seed)

    @classmethod
    def is_model_factory(cls, value: Any) -> bool:
        """Method to determine if a given value is a subclass of ModelFactory"""
        return isclass(value) and issubclass(value, ModelFactory)

    @classmethod
    def is_constrained_field(cls, value: Any) -> bool:
        """Method to determine if a given value is a pydantic Constrained Field"""
        return isclass(value) and any(
            issubclass(value, c)
            for c in [
                ConstrainedBytes,
                ConstrainedDecimal,
                ConstrainedFloat,
                ConstrainedInt,
                ConstrainedList,
                ConstrainedSet,
                ConstrainedStr,
            ]
        )

    @classmethod
    def is_ignored_type(cls, value: Any) -> bool:
        """
        Checks whether a given value is an ignored type

        Note: This method is meant to be overwritten by extension factories and other subclasses
        """
        return value is None

    @classmethod
    def _get_model(cls) -> Type[T]:
        """
        Returns the factory's model
        """
        if not hasattr(cls, "__model__") or not cls.__model__:
            raise ConfigurationError("missing model class in factory Meta")
        model = cls.__model__
        if is_pydantic_model(model):
            cast(BaseModel, model).update_forward_refs()
        return model

    @classmethod
    def _get_sync_persistence(cls) -> SyncPersistenceProtocol[T]:
        """
        Returns a sync_persistence interface if present
        """
        persistence = cls.__sync_persistence__
        if persistence:
            return persistence if not callable(persistence) else persistence()  # pylint: disable=not-callable
        raise ConfigurationError("A sync_persistence handler must be defined in the factory to use this method")

    @classmethod
    def _get_async_persistence(cls) -> AsyncPersistenceProtocol[T]:
        """
        Returns an async_persistence interface
        """
        persistence = cls.__async_persistence__
        if persistence:
            return persistence if not callable(persistence) else persistence()  # pylint: disable=not-callable
        raise ConfigurationError("An async_persistence handler must be defined in the factory to use this method")

    @classmethod
    def _get_faker(cls) -> Faker:
        """
        Returns an instance of faker
        """
        if hasattr(cls, "__faker__") and cls.__faker__:
            return cls.__faker__
        return default_faker

    @classmethod
    def get_provider_map(cls) -> Dict[Any, Callable]:
        """
        Returns a dictionary of <type>:<callable> values

        Note: this method is distinct to allow overriding
        """

        def create_path() -> Path:
            return Path(os.path.realpath(__file__))

        def create_generic_fn() -> Callable:
            return lambda *args: None

        faker = cls._get_faker()

        return {
            # primitives
            object: object,
            float: faker.pyfloat,
            int: faker.pyint,
            bool: faker.pybool,
            str: faker.pystr,
            bytes: create_random_bytes,
            # built-in objects
            dict: faker.pydict,
            tuple: faker.pytuple,
            list: faker.pylist,
            set: faker.pyset,
            frozenset: lambda: frozenset(faker.pylist()),
            deque: lambda: deque(faker.pylist()),
            # standard library objects
            Path: create_path,
            Decimal: faker.pydecimal,
            UUID: uuid4,
            # datetime
            datetime: faker.date_time_between,
            date: faker.date_this_decade,
            time: faker.time,
            timedelta: faker.time_delta,
            # ip addresses
            IPv4Address: faker.ipv4,
            IPv4Interface: faker.ipv4,
            IPv4Network: lambda: faker.ipv4(network=True),
            IPv6Address: faker.ipv6,
            IPv6Interface: faker.ipv6,
            IPv6Network: lambda: faker.ipv6(network=True),
            # types
            Callable: create_generic_fn,
            # pydantic specific
            ByteSize: faker.pyint,
            PositiveInt: faker.pyint,
            FilePath: create_path,
            NegativeFloat: lambda: random.uniform(-100, -1),
            NegativeInt: lambda: faker.pyint() * -1,
            PositiveFloat: faker.pyint,
            NonPositiveFloat: lambda: random.uniform(-100, 0),
            NonNegativeInt: faker.pyint,
            StrictInt: faker.pyint,
            StrictBool: faker.pybool,
            StrictBytes: create_random_bytes,
            StrictFloat: faker.pyfloat,
            StrictStr: faker.pystr,
            DirectoryPath: lambda: create_path().parent,
            EmailStr: faker.free_email,
            NameEmail: faker.free_email,
            PyObject: lambda: "decimal.Decimal",
            Color: faker.hex_color,
            Json: faker.json,
            PaymentCardNumber: faker.credit_card_number,
            AnyUrl: faker.url,
            AnyHttpUrl: faker.url,
            HttpUrl: faker.url,
            PostgresDsn: lambda: "postgresql://user:secret@localhost",
            RedisDsn: lambda: "redis://localhost:6379",
            UUID1: uuid1,
            UUID3: lambda: uuid3(NAMESPACE_DNS, faker.pystr()),
            UUID4: uuid4,
            UUID5: lambda: uuid5(NAMESPACE_DNS, faker.pystr()),
            SecretBytes: create_random_bytes,
            SecretStr: faker.pystr,
            IPvAnyAddress: faker.ipv4,
            IPvAnyInterface: faker.ipv4,
            IPvAnyNetwork: lambda: faker.ipv4(network=True),
            AmqpDsn: lambda: "amqps://",
            KafkaDsn: lambda: "kafka://",
            PastDate: faker.past_date,
            FutureDate: faker.future_date,
            Counter: lambda: Counter(faker.pystr()),
        }

    @classmethod
    def get_mock_value(cls, field_type: Any) -> Any:
        """
        Returns a mock value corresponding to the types supported by pydantic
        see: https://pydantic-docs.helpmanual.io/usage/types/
        """
        handler = cls.get_provider_map().get(field_type)
        if handler is not None:
            return handler()
        raise ParameterError(
            f"Unsupported type: {repr(field_type)}"
            f"\n\nEither extend the providers map or add a factory function for this model field"
        )

    @classmethod
    def handle_constrained_field(cls, model_field: ModelField) -> Any:
        """Handle the built-in pydantic constrained value field types"""
        outer_type = model_field.outer_type_
        try:
            if issubclass(outer_type, ConstrainedFloat):
                return handle_constrained_float(field=cast(ConstrainedFloat, outer_type))
            if issubclass(outer_type, ConstrainedInt):
                return handle_constrained_int(field=cast(ConstrainedInt, outer_type))
            if issubclass(outer_type, ConstrainedDecimal):
                return handle_constrained_decimal(field=cast(ConstrainedDecimal, outer_type))
            if issubclass(outer_type, ConstrainedStr):
                return handle_constrained_string(field=cast(ConstrainedStr, outer_type))
            if issubclass(outer_type, ConstrainedBytes):
                return handle_constrained_bytes(field=cast(ConstrainedBytes, outer_type))
            if issubclass(outer_type, ConstrainedSet) or issubclass(outer_type, ConstrainedList):
                collection_type = list if issubclass(outer_type, ConstrainedList) else set
                return handle_constrained_collection(
                    collection_type=collection_type, model_field=model_field, model_factory=cls  # type: ignore
                )
            raise ParameterError(f"Unknown constrained field: {outer_type.__name__}")  # pragma: no cover
        except AssertionError as e:  # pragma: no cover
            raise ParameterError from e

    @classmethod
    def handle_enum(cls, outer_type: EnumMeta) -> Any:
        """Method that converts an enum to a list and picks a random element out of it"""
        return random.choice(list(outer_type))

    @classmethod
    def handle_factory_field(cls, field_name: str) -> Any:
        """Handles a field defined on the factory class itself"""
        from pydantic_factories.fields import Use

        value = getattr(cls, field_name)
        if isinstance(value, Use):
            return value.to_value()
        if cls.is_model_factory(value):
            return cast(ModelFactory, value).build()
        if callable(value):
            return value()
        return value

    @classmethod
    def create_factory(
        cls,
        model: Type[BaseModel],
        base: Optional[Type["ModelFactory"]] = None,
        **kwargs: Any,
    ) -> "ModelFactory":  # pragma: no cover
        """Dynamically generates a factory given a model"""

        kwargs.setdefault("__faker__", cls._get_faker())
        kwargs.setdefault("__sync_persistence__", cls.__sync_persistence__)
        kwargs.setdefault("__async_persistence__", cls.__async_persistence__)
        kwargs.setdefault("__allow_none_optionals__", cls.__allow_none_optionals__)
        return cast(
            ModelFactory,
            type(
                f"{model.__name__}Factory",
                (base or ModelFactory,),
                {"__model__": model, **kwargs},
            ),
        )

    @classmethod
    def get_field_value(cls, model_field: ModelField) -> Any:
        """Returns a field value on the sub-class if existing, otherwise returns a mock value"""
        if model_field.field_info.const:
            return model_field.get_default()
        if cls.should_set_none_value(model_field=model_field):
            return None
        outer_type = model_field.outer_type_
        if isinstance(outer_type, EnumMeta):
            return cls.handle_enum(outer_type)
        if is_pydantic_model(outer_type) or is_dataclass(outer_type):
            return cls.create_factory(model=outer_type).build()
        if cls.is_constrained_field(outer_type):
            return cls.handle_constrained_field(model_field=model_field)
        if model_field.sub_fields:
            return handle_complex_type(model_field=model_field, model_factory=cls)
        if is_literal(model_field):
            return get_args(outer_type)[0]
        # this is a workaround for the following issue: https://github.com/samuelcolvin/pydantic/issues/3415
        field_type = model_field.type_ if model_field.type_ is not Any else outer_type
        if cls.is_ignored_type(field_type):
            return None
        return cls.get_mock_value(field_type=field_type)

    @classmethod
    def should_set_none_value(cls, model_field: ModelField) -> bool:
        """
        Determines whether a given model field should be set to None

        Separated to its own method to allow easy overriding
        """
        if cls.__allow_none_optionals__:
            return is_optional(model_field=model_field) and not create_random_boolean()
        return False

    @classmethod
    def should_set_field_value(cls, field_name: str, **kwargs: Any) -> bool:
        """
        Ascertain whether to set a value for a given field_name

        Separated to its own method to allow black-listing field names in sub-classes
        """
        is_field_ignored = False
        is_field_in_kwargs = field_name in kwargs
        if hasattr(cls, field_name):
            value = getattr(cls, field_name)
            if isinstance(value, Require) and not is_field_in_kwargs:
                raise MissingBuildKwargError(f"Require kwarg {field_name} is missing")
            is_field_ignored = isinstance(value, Ignore)
        return not is_field_ignored and not is_field_in_kwargs

    @classmethod
    def get_model_fields(cls, model: Type[T]) -> ItemsView[str, ModelField]:
        """
        A function to retrieve the fields of a given model.

        If the model passed is a dataclass, its converted to a pydantic model first.
        """
        if not is_pydantic_model(model):
            model = create_model_from_dataclass(dataclass=model)  # type: ignore
        return model.__fields__.items()  # type: ignore

    @classmethod
    def build(cls, factory_use_construct: bool = False, **kwargs: Any) -> T:
        """
        builds an instance of the factory's __model__

        If factory_use_construct is True, then no validations will be made when instantiating the model,
        see: https://pydantic-docs.helpmanual.io/usage/models/#creating-models-without-validation.

        Note - this is supported only for pydantic models
        """
        for field_name, model_field in cls.get_model_fields(cls._get_model()):
            if model_field.alias:
                field_name = model_field.alias
            if cls.should_set_field_value(field_name, **kwargs):
                if hasattr(cls, field_name):
                    kwargs[field_name] = cls.handle_factory_field(field_name=field_name)
                else:
                    kwargs[field_name] = cls.get_field_value(model_field=model_field)
        if factory_use_construct:
            if is_pydantic_model(cls.__model__):
                return cls.__model__.construct(**kwargs)  # type: ignore
            raise ConfigurationError("factory_use_construct requires a pydantic model as the factory's __model__")
        return cls.__model__(**kwargs)

    @classmethod
    def batch(cls, size: int, **kwargs: Any) -> List[T]:
        """builds a batch of size n of the factory's Meta.model"""
        return [cls.build(**kwargs) for _ in range(size)]

    @classmethod
    def create_sync(cls, **kwargs: Any) -> T:
        """Build and persist a single model instance synchronously"""
        sync_persistence_handler = cls._get_sync_persistence()
        instance = cls.build(**kwargs)
        return sync_persistence_handler.save(data=instance)

    @classmethod
    def create_batch_sync(cls, size: int, **kwargs: Any) -> List[T]:
        """Build and persist a batch of n size model instances synchronously"""
        sync_persistence_handler = cls._get_sync_persistence()
        batch = cls.batch(size, **kwargs)
        return sync_persistence_handler.save_many(data=batch)

    @classmethod
    async def create_async(cls, **kwargs: Any) -> T:
        """Build and persist a single model instance asynchronously"""
        async_persistence_handler = cls._get_async_persistence()
        instance = cls.build(**kwargs)
        return await async_persistence_handler.save(data=instance)

    @classmethod
    async def create_batch_async(cls, size: int, **kwargs: Any) -> List[T]:
        """Build and persist a batch of n size model instances asynchronously"""
        async_persistence_handler = cls._get_async_persistence()
        batch = cls.batch(size, **kwargs)
        return await async_persistence_handler.save_many(data=batch)
