# manual_browser_headers.py
#
# This file is auto-filled with real values from your browser's DevTools (Network tab)
# after logging in to Twitter/X. This will allow your script to make authenticated requests.

def get_headers_and_cookies():
    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": "74fb5ee8dc41670adc0aa4868e062cfad6d2bbe454b3d0569e3c11378cd1a01c7bca754a550048959810bac7fdbda2ff049d20450de7facbd108947bcdd84e475aca826bca0502dc8e72a94a0c5b40d1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
        "referer": "https://x.com/settings/your_twitter_data/account",
        "priority": "u=1, i",
        "sec-ch-ua": '"Microsoft Edge";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-client-transaction-id": "dGaTclzMgnhMW47CRM/9GeOAIbV4TxhHtAehEi///DPVBR1F+LWoyCgQn3BHH2DtGkxLoncXM8OsUJuVQ+LY439hznRZdw",
        "x-client-uuid": "56d8a04f-a3e5-4451-aa40-d2faeac14fa7",
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "en",
        "x-twitter-polling": "true",
    }
    cookies = {
        "guest_id": "v1%3A172701820721628937",
        "night_mode": "2",
        "guest_id_marketing": "v1%3A172701820721628937",
        "guest_id_ads": "v1%3A172701820721628937",
        "personalization_id": "v1_/Sbx62395F5IPHnLTgQ7UA==",
        "g_state": "{\"i_l\":0}",
        "kdt": "Akb5F5QRuziHjAgIuDDOKR2TE2K9t556Es6JvLXd",
        "lang": "en",
        "twid": "u%3D202371331",
        "att": "1-m6rV2PCPDhD4h3hjHrlheffAlTFvEAj8BsxlexkU",
        "des_opt_in": "Y",
        "_gid": "GA1.2.1800424990.1747280147",
        "ph_phc_TXdpocbGVeZVm5VJmAsHTMrCofBQu3e0kN8HGMNGTVW_posthog": "%7B%22distinct_id%22%3A%220196d200-e7f7-7947-94a9-05c83083a0e9%22%2C%22%24sesid%22%3A%5B1747281361383%2C%220196d200-e7f6-789d-aff6-69c1819482a0%22%2C1747279996918%5D%7D",
        "_ga": "GA1.1.1576844488.1747280147",
        "_ga_RJGMY4G45L": "GS2.1.s1747291080$o1$g1$t1747291135$j5$l0$h0",
        "auth_token": "16ab01535e353422b629308185014dca0636f194",
        "ct0": "74fb5ee8dc41670adc0aa4868e062cfad6d2bbe454b3d0569e3c11378cd1a01c7bca754a550048959810bac7fdbda2ff049d20450de7facbd108947bcdd84e475aca826bca0502dc8e72a94a0c5b40d1",
        "_twitter_sess": "BAh7CCIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADofbGFzdF9wYXNzd29yZF9jb25maXJtYXRpb24i%250AFTE3NDcyOTU5NTIzNDIwMDA6HnBhc3N3b3JkX2NvbmZpcm1hdGlvbl91aWQi%250ADjIwMjM3MTMzMQ%253D%253D--a1c82c927e6ba815be52397f80167a7fafe172d5",
        "__cf_bm": ".NfXweSzouU7t2GJ4GbvRzdmWmsVThV784G9gcFnLr4-1747296934-1.0.1.1-Hz.eZYI1pOlxYqdh6_ykjz_lLb_ofBpZ3CfZnRvjQrSM3W0IKHj5bQQBY7tlqd2EPYfaGUnjj7QHNv9fZbpXbhus3mWXYsBSwmUNKtw7rzA",
    }
    return headers, cookies 