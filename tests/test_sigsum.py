def test_integration():
    """Runs some testing as per the example usage as in
    https://www.sigsum.org/getting-started/ :

    > `sigsum-key` will be used to generate a public key-pair.

    > `sigsum-submit` will be used to sign a checksum, submit it to a log, and
      collect its proof of logging.

    > `sigsum-verify` will be used to verify the gathered proof of logging.

    > `sigsum-monitor` will be used to detect that the generated signing key was
      used with Sigsum.

    """
    from devtools import debug

    from sigsum_tools_wrapper import hash_str, sigsum

    SIGSUM_TESTING_POLICY = """\
log 154f49976b59ff09a123675f58cb3e346e0455753c3c3b15d465dcb4f6512b0b https://poc.sigsum.org/jellyfish

witness poc.sigsum.org/nisse 1c25f8a44c635457e2e391d1efbca7d4c2951a0aef06225a881e46b98962ac6c
witness rgdd.se/poc-witness  28c92a5a3a054d317c86fc2eeb6a7ab2054d6217100d0be67ded5b74323c5806

group  demo-quorum-rule any poc.sigsum.org/nisse rgdd.se/poc-witness
quorum demo-quorum-rule
"""
    debug(SIGSUM_TESTING_POLICY)

    key = sigsum.key_generate()
    keyhash = sigsum.key_to_hash(key.pub)
    hexkey = sigsum.key_to_hex(key.pub)

    debug(key.secret, key.pub, keyhash, hexkey)

    messages_str = ["foo", "bar"]
    messages_bytes = [s.encode("utf-8") for s in messages_str]

    msg_str_hashes = [hash_str(m) for m in messages_str]

    debug(messages_str, messages_bytes, msg_str_hashes)

    reqs_regular = sigsum.submit_prepare(
        seckey=key.secret,
        messages=messages_bytes,
        raw_hash=False,
    )
    debug(reqs_regular)

    reqs_raw_hash = sigsum.submit_prepare(
        seckey=key.secret,
        messages=msg_str_hashes,
        raw_hash=True,
    )
    debug(reqs_raw_hash)

    debug(reqs_regular == reqs_raw_hash)
    assert reqs_regular == reqs_raw_hash

    # Now is when we actually generate network activity and interact with the
    # testing server.
    proofs = sigsum.submit_send(policy=SIGSUM_TESTING_POLICY, requests=reqs_raw_hash)
    debug(proofs)

    # Verifying proofs is an all-local operation.

    # With raw_hash as True
    for msg, proof in zip(messages_str, proofs):
        result = sigsum.verify(
            policy=SIGSUM_TESTING_POLICY,
            pubkey=key.pub,
            raw_hash=True,
            message=hash_str(msg),
            proof=proof,
        )
        debug(result, msg, proof)
        assert result is True

    # With raw_hash as False
    for msg, proof in zip(messages_bytes, proofs):
        result = sigsum.verify(
            policy=SIGSUM_TESTING_POLICY,
            pubkey=key.pub,
            raw_hash=False,
            message=msg,
            proof=proof,
        )
        debug(result, msg, proof)
        assert result is True


# TODO: Test rate-limit submit tokens:
#
# "test domain test.sigsum.org, with a public key
# 4cb5abf6ad79fbf5abbccafcc269d85cd2651ed4b885b5869f241aedf0a5ba29 registered
# in DNS. The corresponding private key is
# 0000000000000000000000000000000000000000000000000000000000000001, and it can
# be used by anyone to create valid submit tokens for test purposes."
# https://git.glasklar.is/sigsum/core/log-go/-/blob/main/doc/rate-limit.md#test-domain
