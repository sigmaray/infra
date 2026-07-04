from __future__ import annotations

import pytest

from helpers import REPO_ROOT, docker_compose, ensure_infra_network, remove_path, run

pytestmark = [pytest.mark.ipsec_vpn]


def test_docker_compose_config(docker) -> None:
    docker_compose("config", "--quiet", cwd=REPO_ROOT / "ipsec-vpn")


@pytest.mark.integration
def test_ipsec_vpn_starts_and_listens(docker, ci_env) -> None:
    ipsec_dir = REPO_ROOT / "ipsec-vpn"
    ike_port = ci_env["IPSEC_VPN_IKE_PORT"]
    nat_port = ci_env["IPSEC_VPN_NAT_PORT"]

    try:
        ensure_infra_network()
        remove_path(ipsec_dir / "data")
        docker_compose("up", "-d", "--wait", cwd=ipsec_dir)

        ipsec_status = run(
            "docker",
            "compose",
            "exec",
            "-T",
            "ipsec-vpn",
            "ipsec",
            "status",
            cwd=ipsec_dir,
        )
        assert "pluto_version" in ipsec_status.stdout

        run(
            "docker",
            "compose",
            "exec",
            "-T",
            "ipsec-vpn",
            "sh",
            "-c",
            "for i in $(seq 1 30); do "
            "test -f /etc/ipsec.d/vpnclient.p12 && "
            "test -f /etc/ipsec.d/vpnclient.mobileconfig && exit 0; "
            "sleep 2; done; exit 1",
            cwd=ipsec_dir,
        )

        host_ports = run("ss", "-uln", check=False)
        assert f":{ike_port} " in host_ports.stdout
        assert f":{nat_port} " in host_ports.stdout

        assert (ipsec_dir / "data" / "vpnclient.p12").exists()
        assert (ipsec_dir / "data" / "vpnclient.mobileconfig").exists()
    finally:
        docker_compose("down", cwd=ipsec_dir, check=False)
        remove_path(ipsec_dir / "data")
