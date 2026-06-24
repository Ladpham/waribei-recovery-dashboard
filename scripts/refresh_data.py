#!/usr/bin/env python3
"""
Génère les fichiers JSON pour le dashboard de recouvrement.
Run: python scripts/refresh_data.py
"""
import os, json, sys
from pathlib import Path
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

DB = dict(
    host=os.environ["DB_HOST"],
    port=int(os.environ.get("DB_PORT", 5432)),
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    sslmode=os.environ.get("DB_SSLMODE", "require"),
    connect_timeout=15,
    application_name="recovery-dashboard",
)

OUT = Path(__file__).parent.parent / "docs" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def q(conn, sql, params=None):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def main():
    print(f"[{datetime.now()}] Connexion DB…")
    conn = psycopg2.connect(**DB)

    # ── 1. Config auth ────────────────────────────────────────────────────
    # Mot de passe partagé "waribei2026!" — hash bcrypt généré côté script
    SHARED_HASH = "$2b$12$1QPOgddVZG1Rh/KdJnmwIuM6Vr1Un4zQKtrfIKoapYDhwH9zeGTlK"
    agents = q(conn, """
        SELECT id, name, "displayName"
        FROM "Client"
        WHERE id IN (1089, 2021)
    """)
    config = {
        "agents": [
            {
                "id": a["id"],
                "username": (a["displayName"] or a["name"] or "").lower(),
                "hash": SHARED_HASH,
                "display": a["displayName"] or a["name"],
            }
            for a in agents
        ],
        "slack_webhook": os.environ.get("SLACK_WEBHOOK", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (OUT / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))
    print("  ✓ config.json")

    # ── 2. Transactions PAR 8-30 ──────────────────────────────────────────
    rows = q(conn, """
        WITH photo AS (
            SELECT DISTINCT ON (ud."clientId")
                ud."clientId",
                d."awsUrl"
            FROM "UserDocument" ud
            JOIN "Document" d ON d."userDocumentId" = ud.id
            WHERE d."metaData"->>'type' = 'STORE_PHOTO'
              AND d."awsUrl" IS NOT NULL
              AND d.deleted = false
            ORDER BY ud."clientId", d."createdAt" DESC
        ),
        gps AS (
            SELECT DISTINCT ON ("clientId")
                "clientId", latitude, longitude
            FROM "Localisation"
            WHERE deleted = false
            ORDER BY "clientId", "createdAt" DESC
        ),
        tx_count AS (
            SELECT "merchantId", COUNT(*) as nb_tx
            FROM "Transaction"
            WHERE deleted = false
            GROUP BY "merchantId"
        )
        SELECT
            t.id                               AS tx_id,
            t."merchantId"                     AS merchant_id,
            COALESCE(m."displayName", m.name)  AS merchant_name,
            m.district,
            m."e164"                           AS phone,
            COALESCE(s."displayName", s.name)  AS supplier_name,
            t."totalPrice"                     AS montant,
            t."maturitydDate"::date            AS maturity_date,
            (CURRENT_DATE - t."maturitydDate"::date) AS jours_retard,
            t.type                             AS statut,
            gps.latitude,
            gps.longitude,
            photo."awsUrl"                     AS photo_url,
            COALESCE(tc.nb_tx, 0)              AS nb_tx_historique
        FROM "Transaction" t
        JOIN "Client" m ON t."merchantId" = m.id
        JOIN "Client" s ON t."supplierId" = s.id
        LEFT JOIN photo   ON photo."clientId" = m.id
        LEFT JOIN gps     ON gps."clientId" = m.id
        LEFT JOIN tx_count tc ON tc."merchantId" = m.id
        WHERE t.deleted = false
          AND t.type NOT IN ('CLOSE', 'OVERPAID')
          AND t."maturitydDate" IS NOT NULL
          AND (CURRENT_DATE - t."maturitydDate"::date) BETWEEN 8 AND 30
        ORDER BY jours_retard DESC, t."totalPrice" DESC
    """)

    def serial(v):
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    transactions = [
        {k: serial(v) for k, v in r.items()}
        for r in rows
    ]
    (OUT / "transactions.json").write_text(
        json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "data": transactions},
                   ensure_ascii=False, indent=2)
    )
    print(f"  ✓ transactions.json  ({len(transactions)} tx)")

    # ── 3. Stats hebdomadaires ────────────────────────────────────────────
    stats = q(conn, """
        WITH cohort AS (
            SELECT
                t.id                                            AS tx_id,
                t."merchantId",
                t."totalPrice"                                  AS montant,
                t."maturitydDate"::date                         AS maturity_date,
                (t."maturitydDate"::date + INTERVAL '8 days')::date AS par8_date,
                DATE_TRUNC('week', t."maturitydDate"::date + INTERVAL '8 days')::date AS semaine,
                t.type                                          AS statut,
                t."updatedAt"::date                             AS closed_date
            FROM "Transaction" t
            WHERE t.deleted = false
              AND t."maturitydDate" IS NOT NULL
              AND (t."maturitydDate"::date + INTERVAL '8 days') >= CURRENT_DATE - INTERVAL '12 weeks'
              AND (t."maturitydDate"::date + INTERVAL '8 days') <= CURRENT_DATE
        )
        SELECT
            semaine,
            COUNT(*)                              AS nb_clients,
            SUM(montant)                          AS valeur_totale,
            COUNT(*) FILTER (WHERE statut IN ('CLOSE','OVERPAID'))  AS nb_solds,
            SUM(montant) FILTER (WHERE statut IN ('CLOSE','OVERPAID')) AS montant_recouvre,
            COUNT(*) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date
            )                                     AS recup_j0_nb,
            SUM(montant) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date
            )                                     AS recup_j0_cfa,
            COUNT(*) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date + 3
            )                                     AS recup_j3_nb,
            SUM(montant) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date + 3
            )                                     AS recup_j3_cfa,
            COUNT(*) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date + 7
            )                                     AS recup_j7_nb,
            SUM(montant) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date + 7
            )                                     AS recup_j7_cfa,
            COUNT(*) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date + 15
            )                                     AS recup_j15_nb,
            SUM(montant) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date + 15
            )                                     AS recup_j15_cfa,
            COUNT(*) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date + 30
            )                                     AS recup_j30_nb,
            SUM(montant) FILTER (
                WHERE statut IN ('CLOSE','OVERPAID')
                  AND closed_date <= par8_date + 30
            )                                     AS recup_j30_cfa
        FROM cohort
        GROUP BY semaine
        ORDER BY semaine DESC
        LIMIT 12
    """)

    weekly = [
        {k: (serial(v) if v is not None else None) for k, v in r.items()}
        for r in stats
    ]
    (OUT / "weekly_stats.json").write_text(
        json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "data": weekly},
                   ensure_ascii=False, indent=2)
    )
    print(f"  ✓ weekly_stats.json  ({len(weekly)} semaines)")

    conn.close()
    print("Terminé.")


if __name__ == "__main__":
    main()
