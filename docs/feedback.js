/**
 * Feedback flottant — injecte le bouton + modal sur toutes les pages authentifiées.
 * Poste vers Slack Incoming Webhook (URL dans config.json > slack_webhook).
 */
(function () {
  // ── Styles ──────────────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    #fb-fab {
      position: fixed; bottom: 24px; right: 20px; z-index: 500;
      width: 52px; height: 52px; border-radius: 16px;
      background: #064C72; border: 1.5px solid #0D536E;
      box-shadow: 0 4px 20px rgba(0,0,0,.5);
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; transition: transform .15s, box-shadow .15s;
      font-size: 22px;
    }
    #fb-fab:hover { transform: scale(1.07); box-shadow: 0 6px 28px rgba(0,0,0,.6); }
    #fb-fab:active { transform: scale(.95); }

    #fb-overlay {
      display: none; position: fixed; inset: 0; z-index: 600;
      background: rgba(0,0,0,.6); backdrop-filter: blur(4px);
      align-items: flex-end; justify-content: center;
      padding-bottom: env(safe-area-inset-bottom, 0);
    }
    #fb-overlay.open { display: flex; }

    #fb-sheet {
      background: #07384F; border: 1px solid #0D536E;
      border-radius: 20px 20px 0 0;
      padding: 20px 20px 32px;
      width: 100%; max-width: 480px;
      animation: slideUp .25s ease;
    }
    @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }

    #fb-handle {
      width: 36px; height: 4px; border-radius: 2px;
      background: #0D536E; margin: 0 auto 18px;
    }
    #fb-title {
      font-family: 'DM Sans', sans-serif; font-size: 17px; font-weight: 800;
      color: #F0F9FF; margin-bottom: 4px;
    }
    #fb-sub {
      font-family: 'DM Sans', sans-serif; font-size: 13px; color: #8ECAE6;
      margin-bottom: 16px;
    }
    #fb-textarea {
      width: 100%; min-height: 120px; max-height: 240px;
      background: #04212F; border: 1.5px solid #0D536E; border-radius: 12px;
      color: #F0F9FF; font-family: 'DM Sans', sans-serif; font-size: 15px;
      padding: 14px; outline: none; resize: vertical;
      transition: border-color .2s;
    }
    #fb-textarea:focus { border-color: #8ECAE6; }
    #fb-textarea::placeholder { color: #456E82; }

    #fb-send {
      width: 100%; margin-top: 12px; padding: 14px;
      background: #F83131; color: white; border: none;
      border-radius: 12px; font-family: 'DM Sans', sans-serif;
      font-size: 16px; font-weight: 700; cursor: pointer;
      display: flex; align-items: center; justify-content: center; gap: 8px;
      transition: opacity .15s;
    }
    #fb-send:disabled { opacity: .5; cursor: not-allowed; }
    #fb-send:active:not(:disabled) { opacity: .8; }

    #fb-status {
      margin-top: 10px; text-align: center;
      font-family: 'DM Sans', sans-serif; font-size: 13px;
      min-height: 20px;
    }
    .fb-ok  { color: #4ADE80; }
    .fb-err { color: #F87171; }

    .fb-spinner {
      width: 18px; height: 18px;
      border: 2px solid rgba(255,255,255,.3); border-top-color: white;
      border-radius: 50%; animation: spin .65s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `;
  document.head.appendChild(style);

  // ── DOM ─────────────────────────────────────────────────────────────────
  const fab = document.createElement('div');
  fab.id = 'fb-fab';
  fab.title = 'Envoyer un feedback';
  fab.textContent = '💬';
  document.body.appendChild(fab);

  const overlay = document.createElement('div');
  overlay.id = 'fb-overlay';
  overlay.innerHTML = `
    <div id="fb-sheet">
      <div id="fb-handle"></div>
      <div id="fb-title">Ton avis compte 💡</div>
      <div id="fb-sub">Un problème, une idée, quelque chose à améliorer ?</div>
      <textarea id="fb-textarea" placeholder="Écris ton message ici…" maxlength="1000"></textarea>
      <button id="fb-send">Envoyer à Ladislas</button>
      <div id="fb-status"></div>
    </div>`;
  document.body.appendChild(overlay);

  // ── Events ──────────────────────────────────────────────────────────────
  fab.addEventListener('click', () => {
    overlay.classList.add('open');
    document.getElementById('fb-textarea').focus();
  });
  overlay.addEventListener('click', e => {
    if (e.target === overlay) overlay.classList.remove('open');
  });

  document.getElementById('fb-send').addEventListener('click', send);
  document.getElementById('fb-textarea').addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.metaKey) send();
  });

  // ── Send ────────────────────────────────────────────────────────────────
  async function send() {
    const text = document.getElementById('fb-textarea').value.trim();
    if (!text) return;

    const btn = document.getElementById('fb-send');
    const status = document.getElementById('fb-status');
    btn.disabled = true;
    btn.innerHTML = '<div class="fb-spinner"></div> Envoi…';
    status.textContent = '';
    status.className = '';

    try {
      const cfg = await fetch('data/config.json?_=' + Date.now()).then(r => r.json());
      const slack_webhook = (cfg.sw_a || '') + (cfg.sw_b || '') + (cfg.sw_c || '');
      if (!slack_webhook || slack_webhook.length < 60) throw new Error('Webhook non configuré');

      const agent = JSON.parse(sessionStorage.getItem('wr_agent') || '{}');
      const page = {
        'operations.html': 'Liste opérations',
        'map.html': 'Carte',
        'resultats.html': 'Stats',
      }[location.pathname.split('/').pop()] || location.pathname;

      const now = new Date().toLocaleString('fr-FR', {
        weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
      });

      const payload = {
        channel: '#general',
        blocks: [
          {
            type: 'section',
            text: {
              type: 'mrkdwn',
              text: `💬 *Feedback agent — ${agent.display || 'inconnu'}*\n📅 ${now}  ·  📱 ${page}`,
            },
          },
          { type: 'divider' },
          {
            type: 'section',
            text: { type: 'mrkdwn', text: `> ${text.replace(/\n/g, '\n> ')}` },
          },
        ],
      };

      const res = await fetch(slack_webhook, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      if (!res.ok && res.status !== 200) throw new Error('Slack error ' + res.status);

      status.textContent = '✅ Message envoyé !';
      status.className = 'fb-ok';
      document.getElementById('fb-textarea').value = '';
      setTimeout(() => overlay.classList.remove('open'), 1800);
    } catch (e) {
      status.textContent = '⚠️ Erreur d\'envoi — réessaie.';
      status.className = 'fb-err';
      console.error(e);
    } finally {
      btn.disabled = false;
      btn.innerHTML = 'Envoyer à Ladislas';
    }
  }
})();
