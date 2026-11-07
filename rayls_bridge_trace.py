"""
rayls_bridge_trace.py (v3) - follows one dollar through the Rayls bridge. Read-only, no wallet.
Docs claim:  USDC locked on Ethereum -> USDC.e minted on Rayls -> USDC.e locked in escrow -> USDr minted.
This script reads every hop and prints a reconciliation table, and shows who can mint USDC.e.
Python 3 standard library only.
  python rayls_bridge_trace.py                normal run
  python rayls_bridge_trace.py --negative     same checks, one hex digit of the USDC.e address changed
  python rayls_bridge_trace.py --skip-logs    skip the slow event scan (step 2)
Writes bridge_trace_evidence.json next to the script.
"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

RAYLS_RPC = os.environ.get("RAYLS_RPC", "https://mainnet-rpc.rayls.com/")
EXPLORER = os.environ.get("RAYLS_EXPLORER", "https://explorer.rayls.com")
ETH_RPCS = [os.environ["ETH_RPC"]] if os.environ.get("ETH_RPC") else [
    "https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com",
    "https://rpc.ankr.com/eth", "https://cloudflare-eth.com"]
UA = {"User-Agent": "Mozilla/5.0 (rayls-bridge-trace)", "Content-Type": "application/json"}

USDC_E   = "0x9001dbe4D68d36ab87923A2a9Dfb0c745fd25001"   # docs.rayls.com/docs/bridging-to-the-public-chain
ESCROW   = "0xD19A5e28FEd41FA289E92Ae61B9Bc5BD883DB0D2"   # USDrEscrow proxy (from anazoro001/rayls-usdr-backing-research)
USDR     = "0x0000000000000000000000000000000000000400"   # USDr gas token
ETH_POOL = "0xc026395860Db2d07ee33e05fE50ed7bD583189C7"   # Ethereum pool named in the same research
ETH_USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"   # Circle USDC on Ethereum
OTHERS   = [("USDT0.s", "0x1343994e136B6b15CBB2eB4075e0E73b8c4Ebce0"),
            ("WETH",    "0xd8cF92E9B6Fae6B32f795AcB11Edd50E8dD6Ff4d")]
SEL = dict(name="0x06fdde03", symbol="0x95d89b41", decimals="0x313ce567", totalSupply="0x18160ddd",
           balanceOf="0x70a08231", owner="0x8da5cb5b", token="0xfc0c546a",
           circulatingUSDr="0x5159e6de", requiredUsdcEBacking="0x27a95a88",
           withdrawableSurplus="0xb6739070", minterBurner="0x2ef8c5a4",
           getThreshold="0xe75235b8", getOwners="0xa0e67e2b", getMinDelay="0xf27a0c92")
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO_T = "0x" + "0" * 64
HERE = os.path.dirname(os.path.abspath(__file__))

class NoData(Exception): pass

def rpc(urls, method, params):
    last = None
    for u in urls:
        try:
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
            out = json.loads(urllib.request.urlopen(urllib.request.Request(u, body, UA), timeout=40).read().decode())
            if "error" in out:
                raise NoData(str(out["error"].get("message", "error")))
            return out["result"]
        except NoData: raise
        except Exception as e: last = e
    raise RuntimeError("RPC unreachable: %s" % last)

def call(urls, to, sel, args=""):
    try:
        r = rpc(urls, "eth_call", [{"to": to, "data": SEL[sel] + args}, "latest"])
    except NoData: return None
    return None if r in (None, "0x") else r[2:]

def u256(h, i=0): return int(h[i*64:(i+1)*64], 16)
def addr(h, i=0): return "0x" + h[i*64+24:(i+1)*64]
def pad(a): return a.lower().replace("0x", "").rjust(64, "0")
def text(h):
    if len(h) == 64: return bytes.fromhex(h).rstrip(b"\x00").decode("utf-8", "replace")
    o = int(h[:64], 16) * 2; n = int(h[o:o+64], 16)
    return bytes.fromhex(h[o+64:o+64+n*2]).decode("utf-8", "replace")
def fmt(v, d): return f"{v/10**d:,.6f}"

def kind_of(urls, a):
    code = rpc(urls, "eth_getCode", [a, "latest"])
    if code in ("0x", None): return "EOA (a normal wallet, no contract code)", {}
    extra = {"code_bytes": (len(code) - 2) // 2}
    th = call(urls, a, "getThreshold")
    if th:
        ow = call(urls, a, "getOwners"); n = int(ow[64:128], 16) if ow else 0
        extra.update(threshold=u256(th), owners=n)
        return f"Safe multisig, threshold {u256(th)} of {n} owners", extra
    md = call(urls, a, "getMinDelay")
    if md: extra["min_delay_s"] = u256(md); return f"timelock, min delay {u256(md)} s", extra
    return f"contract ({extra['code_bytes']:,} bytes), not a Safe or timelock by interface", extra

def getj(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]}), timeout=30).read().decode())

ev = {"run_utc": time.strftime("%d %b %Y %H:%M UTC", time.gmtime()), "steps": {}}
neg = "--negative" in sys.argv
usdc_e = USDC_E if not neg else USDC_E[:-1] + ("2" if USDC_E[-1] != "2" else "3")
L = "=" * 74
print(L); print("Rayls bridge trace | read-only | " + ev["run_utc"] + ("  | NEGATIVE TEST" if neg else "")); print(L)
try:
    latest = int(rpc([RAYLS_RPC], "eth_blockNumber", []), 16)
    print(f"Rayls RPC: chain id {int(rpc([RAYLS_RPC],'eth_chainId',[]),16)}  block {latest:,}")
    ev["rayls_block"] = latest
except Exception as e:
    print("Cannot reach Rayls RPC:", e); sys.exit(1)
R = [RAYLS_RPC]

# STEP 1 ---------------------------------------------------------------
print("\nSTEP 1  Who can mint USDC.e on Rayls?"); print("  token:", usdc_e)
code = rpc(R, "eth_getCode", [usdc_e, "latest"])
if code in ("0x", None):
    print("  NO contract code at this address -> every later step is meaningless. Check stops here.")
    ev["steps"]["1"] = {"address": usdc_e, "has_code": False}
    json.dump(ev, open(os.path.join(HERE, "bridge_trace_negative.json"), "w"), indent=2)
    sys.exit(0)
sup = u256(call(R, usdc_e, "totalSupply")); dec = u256(call(R, usdc_e, "decimals"))
own = call(R, usdc_e, "owner"); owner = addr(own) if own else None
print(f"  name {text(call(R, usdc_e, 'name'))} | decimals {dec} | totalSupply {fmt(sup, dec)}")
print(f"  owner(): {owner}")
s1 = {"address": usdc_e, "has_code": True, "totalSupply": sup / 10**dec, "owner": owner}
if owner:
    k, extra = kind_of(R, owner); print(f"  owner is: {k}"); s1["owner_kind"] = k; s1.update(extra)
for label, a in OTHERS:
    o = call(R, a, "owner"); s1[label + "_owner"] = addr(o) if o else None
    print(f"  {label} owner(): {addr(o) if o else 'not exposed'}   same owner as USDC.e: {bool(o) and addr(o).lower() == (owner or '').lower()}")
ev["steps"]["1"] = s1

# STEP 2 ---------------------------------------------------------------
print("\nSTEP 2  Mint and burn events of USDC.e (Transfer from / to the zero address)")
if "--skip-logs" in sys.argv:
    print("  skipped by --skip-logs"); ev["steps"]["2"] = {"skipped": "flag"}
else:
    DEADLINE = time.time() + 240
    def logs(topics, lo, hi):
        return rpc(R, "eth_getLogs", [{"address": usdc_e, "fromBlock": hex(lo), "toBlock": hex(hi), "topics": topics}])
    def scan(topics, tag, step):
        ranges = [(b, min(latest, b + step - 1)) for b in range(0, latest + 1, step)]
        out, done = [], 0
        with ThreadPoolExecutor(8) as ex:
            futs = [ex.submit(logs, topics, a, b) for a, b in ranges]
            for f in futs:
                left = DEADLINE - time.time()
                if left <= 0: raise TimeoutError
                out += f.result(timeout=left); done += 1
                print(f"    {tag}: chunk {done}/{len(ranges)}  events so far {len(out)}", end="\r", flush=True)
        print()
        return out
    try:
        step = 40_000
        try: logs([TRANSFER, ZERO_T], 0, step - 1)
        except NoData: step = 10_000
        mints = scan([TRANSFER, ZERO_T], "mints", step)
        print(f"  mint events found: {len(mints)}")
        for x in mints[:10]:
            to = addr(x["topics"][2][2:]); amt = int(x["data"], 16)
            print(f"    block {int(x['blockNumber'],16):,}  to {to}  amount {fmt(amt, dec)}  tx {x['transactionHash']}")
        burns = scan([TRANSFER, None, ZERO_T], "burns", step)
        m = sum(int(x["data"], 16) for x in mints); bn = sum(int(x["data"], 16) for x in burns)
        print(f"  total minted {fmt(m, dec)} | burn events {len(burns)} total burned {fmt(bn, dec)}")
        print(f"  minted - burned = {fmt(m-bn, dec)}   vs totalSupply {fmt(sup, dec)}   match: {m-bn == sup}")
        ev["steps"]["2"] = {"mint_events": len(mints), "burn_events": len(burns), "minted": m / 10**dec,
                            "burned": bn / 10**dec, "net_equals_supply": (m - bn == sup),
                            "mints": [{"block": int(x["blockNumber"], 16), "tx": x["transactionHash"],
                                       "to": addr(x["topics"][2][2:]), "amount": int(x["data"], 16) / 10**dec} for x in mints[:50]]}
    except (TimeoutError, Exception) as e:
        print("\n  step 2 incomplete:", type(e).__name__, e)
        ev["steps"]["2"] = {"incomplete": str(e)}

# STEP 3 ---------------------------------------------------------------
print("\nSTEP 3  Escrow: USDC.e locked vs USDr issued (Rayls side)")
try:
    esc = u256(call(R, usdc_e, "balanceOf", pad(ESCROW)))
    usdr = u256(call(R, USDR, "totalSupply"))
    print(f"  USDC.e held by escrow {ESCROW}: {fmt(esc, 6)}")
    print(f"  USDr totalSupply (gas token {USDR}): {fmt(usdr, 18)}")
    s3 = {"escrow_usdc_e": esc / 1e6, "usdr_supply": usdr / 1e18}
    for k in ("circulatingUSDr", "requiredUsdcEBacking", "withdrawableSurplus"):
        r = call(R, ESCROW, k)
        if r: print(f"  escrow.{k}(): {u256(r) / (1e18 if k == 'circulatingUSDr' else 1e6):,.6f}"); s3[k] = u256(r)
    mb = call(R, ESCROW, "minterBurner")
    if mb:
        mba = addr(mb); kk, _ = kind_of(R, mba); print(f"  escrow.minterBurner(): {mba}  ({kk})"); s3["minterBurner"] = mba; s3["minterBurner_kind"] = kk
    print(f"  USDC.e supply {fmt(sup, 6)}  -  escrow {fmt(esc, 6)}  =  {fmt(sup - esc, 6)} USDC.e outside the escrow")
    print(f"  escrow USDC.e - USDr supply = {(esc/1e6) - (usdr/1e18):,.6f}")
    s3["usdc_e_outside_escrow"] = (sup - esc) / 1e6; ev["steps"]["3"] = s3
except Exception as e:
    print("  failed:", e); ev["steps"]["3"] = {"error": str(e)}

# STEP 4 ---------------------------------------------------------------
print("\nSTEP 4  Who holds USDC.e (Rayls explorer API, Blockscout)")
try:
    c = getj(f"{EXPLORER}/api/v2/tokens/{usdc_e}/counters")
    print(f"  holders: {c.get('token_holders_count')}   transfers: {c.get('transfers_count')}")
    h = getj(f"{EXPLORER}/api/v2/tokens/{usdc_e}/holders")
    rows = []
    for it in h.get("items", [])[:8]:
        a = it["address"]["hash"]; v = int(it["value"]); rows.append({"address": a, "value": v / 10**dec})
        print(f"    {a}  {fmt(v, dec)}  ({v/sup*100:.2f}% of supply)")
    ev["steps"]["4"] = {"holders": c.get("token_holders_count"), "transfers": c.get("transfers_count"), "top": rows}
except Exception as e:
    print("  explorer API not reachable:", e); ev["steps"]["4"] = {"error": str(e)}

# STEP 5 ---------------------------------------------------------------
print("\nSTEP 5  Ethereum side: USDC held by the pool the research names")
try:
    bal = u256(call(ETH_RPCS, ETH_USDC, "balanceOf", pad(ETH_POOL)))
    code = rpc(ETH_RPCS, "eth_getCode", [ETH_POOL, "latest"]); tk = call(ETH_RPCS, ETH_POOL, "token")
    print(f"  pool {ETH_POOL}  contract code: {'yes' if code not in ('0x', None) else 'NO'}")
    print(f"  pool.token(): {addr(tk) if tk else 'not exposed'}")
    print(f"  USDC held by the pool: {fmt(bal, 6)}")
    print(f"  Rayls USDC.e supply:   {fmt(sup, 6)}")
    print("  NOTE: the pool is shared with other chains. Its balance cannot be split per chain from balances alone.")
    ev["steps"]["5"] = {"pool_usdc": bal / 1e6, "pool_token": addr(tk) if tk else None, "rayls_usdc_e_supply": sup / 1e6}
except Exception as e:
    print("  failed:", e); ev["steps"]["5"] = {"error": str(e)}

p = os.path.join(HERE, "bridge_trace_evidence.json" if not neg else "bridge_trace_negative.json")
json.dump(ev, open(p, "w"), indent=2)
print("\n" + L); print("Saved all values to", p); print(L)
