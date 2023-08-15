from collections.abc import (
    Mapping,
)
from typing import (
    Any,
    Dict,
    NamedTuple,
    Union,
)
import warnings

from eth_typing import (
    Address,
    Hash32,
)
from eth_utils.curried import (
    ValidationError,
    keccak,
    text_if_str,
    to_bytes,
    to_canonical_address,
    to_text,
)
from hexbytes import (
    HexBytes,
)

from eth_account._utils.encode_typed_data.encoding_and_hashing import (
    hash_domain,
    hash_EIP712_message,
)
from eth_account._utils.structured_data.hashing import (
    hash_domain as hash_eip712_domain,
    hash_message as hash_eip712_message,
    load_and_validate_structured_message,
)
from eth_account._utils.structured_data.validation import (
    validate_structured_data,
)
from eth_account._utils.validation import (
    is_valid_address,
)

text_to_bytes = text_if_str(to_bytes)


# watch for updates to signature format
class SignableMessage(NamedTuple):
    """
    A message compatible with EIP-191_ that is ready to be signed.

    The properties are components of an EIP-191_ signable message. Other message formats
    can be encoded into this format for easy signing. This data structure doesn't need
    to know about the original message format. For example, you can think of
    EIP-712 as compiling down to an EIP-191 message.

    In typical usage, you should never need to create these by hand. Instead, use
    one of the available encode_* methods in this module, like:

        - :meth:`encode_structured_data`
        - :meth:`encode_intended_validator`
        - :meth:`encode_defunct`

    .. _EIP-191: https://eips.ethereum.org/EIPS/eip-191
    """

    version: bytes  # must be length 1
    header: bytes  # aka "version specific data"
    body: bytes  # aka "data to sign"


def _hash_eip191_message(signable_message: SignableMessage) -> Hash32:
    version = signable_message.version
    if len(version) != 1:
        raise ValidationError(
            f"The supplied message version is {version!r}. "
            "The EIP-191 signable message standard only supports one-byte versions."
        )

    joined = b"\x19" + version + signable_message.header + signable_message.body
    return Hash32(keccak(joined))


# watch for updates to signature format
def encode_intended_validator(
    validator_address: Union[Address, str],
    primitive: bytes = None,
    *,
    hexstr: str = None,
    text: str = None,
) -> SignableMessage:
    """
    Encode a message using the "intended validator" approach (ie~ version 0)
    defined in EIP-191_.

    Supply the message as exactly one of these three arguments:
    bytes as a primitive, a hex string, or a unicode string.

    .. WARNING:: Note that this code has not gone through an external audit.

    :param validator_address: which on-chain contract is capable of validating this
        message, provided as a checksummed address or in native bytes.
    :param primitive: the binary message to be signed
    :type primitive: bytes or int
    :param str hexstr: the message encoded as hex
    :param str text: the message as a series of unicode characters (a normal Py3 str)
    :returns: The EIP-191 encoded message, ready for signing

    .. _EIP-191: https://eips.ethereum.org/EIPS/eip-191
    """
    if not is_valid_address(validator_address):
        raise ValidationError(
            f"Cannot encode message with 'Validator Address': {validator_address!r}. "
            "It must be a checksum address, or an address converted to bytes."
        )
    # The validator_address is a str or Address (which is a subtype of bytes). Both of
    # these are AnyStr, which includes str and bytes.
    # Not sure why mypy complains here...
    canonical_address = to_canonical_address(validator_address)
    message_bytes = to_bytes(primitive, hexstr=hexstr, text=text)
    return SignableMessage(
        HexBytes(b"\x00"),  # version 0, as defined in EIP-191
        canonical_address,
        message_bytes,
    )


def encode_structured_data(
    primitive: Union[bytes, int, Mapping] = None,
    *,
    hexstr: str = None,
    text: str = None,
) -> SignableMessage:
    r"""

    .. WARNING:: This method is deprecated. Use :meth:`encode_typed_data` instead.

    Encode an EIP-712_ message.

    See :meth:`encode_structured_data_legacy` for usage.

    """
    warnings.warn(
        "`encode_structured_data` is deprecated and will be removed in a"
        " future release. Use encode_typed_data instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return encode_structured_data_legacy(primitive, hexstr=hexstr, text=text)


def encode_structured_data_legacy(
    primitive: Union[bytes, int, Mapping] = None,
    *,
    hexstr: str = None,
    text: str = None,
) -> SignableMessage:
    r"""

    .. WARNING:: This method is deprecated. Use :meth:`encode_typed_data` instead.

    Encode an EIP-712_ message.

    EIP-712 is the "structured data" approach (ie~ version 1 of an EIP-191 message).

    Supply the message as exactly one of the three arguments:

        - primitive, as a dict that defines the structured data
        - primitive, as bytes
        - text, as a json-encoded string
        - hexstr, as a hex-encoded (json-encoded) string

    .. WARNING:: Note that this code has not gone through an external audit, and
        the test cases are incomplete.

    :param primitive: the binary message to be signed
    :type primitive: bytes or int or Mapping (eg~ dict )
    :param hexstr: the message encoded as hex
    :param text: the message as a series of unicode characters (a normal Py3 str)
    :returns: The EIP-191 encoded message, ready for signing


    Usage Notes:
     - An EIP712 message consists of 4 top-level keys: ``types``, ``primaryType``,
       ``domain``, and ``message``. All 4 must be present to encode properly.
     - The key ``EIP712Domain`` must be present within ``types``.
     - The `type` of a field may be a Solidity type or a `custom` type, i.e., one
       that is defined within the ``types`` section of the typed data.
     - Extra information in ``message`` and ``domain`` will be ignored when encoded.
       For example, if the custom type ``Person`` defines the fields ``name`` and
       ``wallet``, but an additional ``id`` field is provided in ``message``, the
       resulting encoding will be the same as if the ``id`` information was not present.
     - Unused custom types will be ignored in the same way.

    .. doctest:: python

        >>> # an example of basic usage
        >>> import json
        >>> from eth_account import Account
        >>> from eth_account.messages import encode_structured_data

        >>> typed_data = {
        ...     "types": {
        ...         "EIP712Domain": [
        ...             {"name": "name", "type": "string"},
        ...             {"name": "version", "type": "string"},
        ...             {"name": "chainId", "type": "uint256"},
        ...             {"name": "verifyingContract", "type": "address"},
        ...         ],
        ...         "Person": [
        ...             {"name": "name", "type": "string"},
        ...             {"name": "wallet", "type": "address"},
        ...         ],
        ...         "Mail": [
        ...             {"name": "from", "type": "Person"},
        ...             {"name": "to", "type": "Person"},
        ...             {"name": "contents", "type": "string"},
        ...         ],
        ...     },
        ...     "primaryType": "Mail",
        ...     "domain": {
        ...         "name": "Ether Mail",
        ...         "version": "1",
        ...         "chainId": 1,
        ...         "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC",
        ...     },
        ...     "message": {
        ...         "from": {
        ...             "name": "Cow",
        ...             "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826"
        ...         },
        ...         "to": {
        ...             "name": "Bob",
        ...             "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB"
        ...         },
        ...         "contents": "Hello, Bob!",
        ...     },
        ... }

        >>> key = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

        >>> signable_msg_from_dict = encode_structured_data(typed_data)
        >>> signable_msg_from_str = encode_structured_data(text=json.dumps(typed_data))
        >>> signable_msg_from_hexstr = encode_structured_data(
        ...     hexstr=json.dumps(typed_data).encode("utf-8").hex()
        ... )

        >>> signed_msg_from_dict = Account.sign_message(signable_msg_from_dict, key)
        >>> signed_msg_from_str = Account.sign_message(signable_msg_from_str, key)
        >>> signed_msg_from_hexstr = Account.sign_message(signable_msg_from_hexstr, key)

        >>> signed_msg_from_dict == signed_msg_from_str == signed_msg_from_hexstr
        True
        >>> signed_msg_from_dict.messageHash
        HexBytes('0xbe609aee343fb3c4b28e1df9e632fca64fcfaede20f02e86244efddf30957bd2')

    .. _EIP-712: https://eips.ethereum.org/EIPS/eip-712
    """
    if isinstance(primitive, Mapping):
        validate_structured_data(primitive)
        structured_data = primitive
    else:
        message_string = to_text(primitive, hexstr=hexstr, text=text)
        structured_data = load_and_validate_structured_message(message_string)
    return SignableMessage(
        HexBytes(b"\x01"),
        hash_eip712_domain(structured_data),
        hash_eip712_message(structured_data),
    )


def encode_defunct(
    primitive: bytes = None, *, hexstr: str = None, text: str = None
) -> SignableMessage:
    r"""
    Encode a message for signing, using an old, unrecommended approach.

    Only use this method if you must have compatibility with
    :meth:`w3.eth.sign() <web3.eth.Eth.sign>`.

    EIP-191 defines this as "version ``E``".

    .. NOTE: This standard includes the number of bytes in the message as a part of
        the header. Awkwardly, the number of bytes in the message is encoded in
        decimal ascii. So if the message is 'abcde', then the length is encoded
        as the ascii character '5'. This is one of the reasons that this message
        format is not preferred. There is ambiguity when the message '00' is
        encoded, for example.

    Supply exactly one of the three arguments: bytes, a hex string, or a unicode string.

    :param primitive: the binary message to be signed
    :type primitive: bytes or int
    :param str hexstr: the message encoded as hex
    :param str text: the message as a series of unicode characters (a normal Py3 str)
    :returns: The EIP-191 encoded message, ready for signing

    .. doctest:: python

        >>> from eth_account.messages import encode_defunct
        >>> from eth_utils.curried import to_hex, to_bytes

        >>> message_text = "I♥SF"
        >>> encode_defunct(text=message_text)
        SignableMessage(version=b'E',
                        header=b'thereum Signed Message:\n6',
                        body=b'I\xe2\x99\xa5SF')

        These four also produce the same hash:
        >>> encode_defunct(to_bytes(text=message_text))
        SignableMessage(version=b'E',
                        header=b'thereum Signed Message:\n6',
                        body=b'I\xe2\x99\xa5SF')

        >>> encode_defunct(bytes(message_text, encoding='utf-8'))
        SignableMessage(version=b'E',
                        header=b'thereum Signed Message:\n6',
                        body=b'I\xe2\x99\xa5SF')

        >>> to_hex(text=message_text)
        '0x49e299a55346'
        >>> encode_defunct(hexstr='0x49e299a55346')
        SignableMessage(version=b'E',
                        header=b'thereum Signed Message:\n6',
                        body=b'I\xe2\x99\xa5SF')

        >>> encode_defunct(0x49e299a55346)
        SignableMessage(version=b'E',
                        header=b'thereum Signed Message:\n6',
                        body=b'I\xe2\x99\xa5SF')
    """
    message_bytes = to_bytes(primitive, hexstr=hexstr, text=text)
    msg_length = str(len(message_bytes)).encode("utf-8")

    # Encoding version E defined by EIP-191
    return SignableMessage(
        b"E",
        b"thereum Signed Message:\n" + msg_length,
        message_bytes,
    )


def defunct_hash_message(
    primitive: bytes = None, *, hexstr: str = None, text: str = None
) -> HexBytes:
    """
    Convert the provided message into a message hash, to be signed.

    .. CAUTION:: Intended for use with the deprecated
        :meth:`eth_account.account.Account.signHash`.
        This is for backwards compatibility only. All new implementations
        should use :meth:`encode_defunct` instead.

    :param primitive: the binary message to be signed
    :type primitive: bytes or int
    :param str hexstr: the message encoded as hex
    :param str text: the message as a series of unicode characters (a normal Py3 str)
    :returns: The hash of the message, after adding the prefix
    """
    signable = encode_defunct(primitive, hexstr=hexstr, text=text)
    hashed = _hash_eip191_message(signable)
    return HexBytes(hashed)


def encode_typed_data(
    domain_data: Dict[Any, Any],
    message_types: Dict[Any, Any],
    message_data: Dict,
) -> SignableMessage:
    r"""
    Encode an EIP-712_ message in a manner compatible with other implementations
    in use, such as the Metamask and Ethers ``signTypedData`` functions.

    Supply the message as exactly three arguments:

        - ``domain_data``, a dict of the EIP-712 domain data
        - ``message_types``, a dict of custom types
        - ``message_data``, a dict of the data to be signed

    .. WARNING:: Note that this code has not gone through an external audit, and
        the test cases are incomplete.

    Usage Notes:
        - ``message_types`` should not include the ``EIP712Domain`` key. It will be
            derived from ``domain_data``.

    Type Coercion:
        - For fixed-size bytes types, smaller values will be padded to fit in larger
          types, but values larger than the type will raise ``ValueOutOfBounds``.
          e.g., an 8-byte value will be padded to fit a ``bytes16`` type, but 16-byte
          value provided for a ``bytes8`` type will raise an error.
        - ``bool`` types will also accept ``int``s 0 and 1, ``bytes`` objects
          ``b"\x00"`` and ``b"\x01"``, and strings such as ``"0"`` or ``"1"``, ``"OxO"``
          or ``"0x1"``, ``"true"`` or ``"false"``, and ``True`` or ``False``.
        - ``int`` and ``uint`` types will also accept strings. If prefixed with ``"0x"``
          , the string will be interpreted as hex. Otherwise, it will be interpreted as
          decimal.

    Differences from ``signTypedData``:
        - Custom types that are not alphanumeric will encode differently.
        - Custom types that are used but not defined in ``types`` will not encode.

    :param domain_data: EIP712 domain data
    :param message_types: custom types used by the `value` data
    :param message_data: data to be signed
    :returns: a ``SignableMessage``, an encoded message ready to be signed


    .. doctest:: python

        >>> # an example of basic usage
        >>> import json
        >>> from eth_account import Account
        >>> from eth_account.messages import encode_typed_data

        >>> # all domain properties are optional
        >>> domain_data = {
        ...     "name": "Ether Mail",
        ...     "version": "1",
        ...     "chainId": 1,
        ...     "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC",
        ...     "salt": b"decafbeef",
        ... }
        >>> # custom types
        >>> msg_types = {
        ...     "Person": [
        ...         {"name": "name", "type": "string"},
        ...         {"name": "wallet", "type": "address"},
        ...     ],
        ...     "Mail": [
        ...         {"name": "from", "type": "Person"},
        ...         {"name": "to", "type": "Person"},
        ...         {"name": "contents", "type": "string"},
        ...     ],
        ... }
        >>> # the data to be signed
        >>> msg_data = {
        ...     "from": {
        ...         "name": "Cow",
        ...         "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826",
        ...     },
        ...     "to": {
        ...         "name": "Bob",
        ...         "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB",
        ...     },
        ...     "contents": "Hello, Bob!",
        ... }
        >>> key = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        >>> signable_msg = encode_typed_data(domain_data, msg_types, msg_data)
        >>> signed_msg = Account.sign_message(signable_msg, key)
        >>> signed_msg.messageHash
        HexBytes('0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530')
    .. _EIP-712: https://eips.ethereum.org/EIPS/eip-712
    """
    return SignableMessage(
        HexBytes(b"\x01"),
        hash_domain(domain_data),
        hash_EIP712_message(message_types, message_data),
    )
