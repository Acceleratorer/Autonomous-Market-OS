(() => {
  const state = document.querySelector("#state");
  const summary = document.querySelector("#summary");
  const workspace = document.querySelector("#workspace");
  const actions = document.querySelector("#actions");
  const riskOlder = document.querySelector("#risk-older");
  const riskLatest = document.querySelector("#risk-latest");
  const riskPageStatus = document.querySelector("#risk-page-status");
  const orderOlder = document.querySelector("#order-older");
  const orderLatest = document.querySelector("#order-latest");
  const orderPageStatus = document.querySelector("#order-page-status");
  const memberOlder = document.querySelector("#member-older");
  const memberLatest = document.querySelector("#member-latest");
  const memberPageStatus = document.querySelector("#member-page-status");
  const reservationOlder = document.querySelector("#reservation-older");
  const reservationLatest = document.querySelector("#reservation-latest");
  const reservationPageStatus = document.querySelector("#reservation-page-status");
  const portfolioId = decodeURIComponent(location.pathname.split("/").filter(Boolean)[1] || "");
  const activeCursors = { risk: null, order: null, member: null, reservation: null };

  const text = (selector, value) => { document.querySelector(selector).textContent = String(value ?? "—"); };
  const fail = (message) => {
    state.textContent = message;
    state.className = "state error";
  };

  const display = (selector, value) => text(selector, value === undefined || value === null || value === "" ? "—" : value);
  const cell = (row, value) => {
    const element = document.createElement("td");
    element.textContent = String(value ?? "—");
    row.appendChild(element);
  };
  const renderOrders = (page) => {
    const orders = page.orders || [];
    const target = document.querySelector("#orders-table");
    target.replaceChildren();
    document.querySelector("#orders-empty").hidden = orders.length !== 0;
    for (const order of orders) {
      const row = document.createElement("tr");
      cell(row, order.order_id);
      cell(row, order.strategy_id);
      cell(row, order.side);
      cell(row, order.order_type);
      cell(row, order.quantity);
      cell(row, order.state);
      target.appendChild(row);
    }
    const pageInfo = page.page || {};
    activeCursors.order = pageInfo.before_order_id || null;
    orderPageStatus.textContent = activeCursors.order
      ? `Older orders before ${activeCursors.order}.`
      : `Showing the latest ${orders.length} orders.`;
    orderPageStatus.hidden = orders.length === 0;
    orderLatest.hidden = !activeCursors.order;
    orderOlder.hidden = !pageInfo.has_more;
    orderOlder.onclick = () => loadInspectionPages({ order: pageInfo.next_before_order_id });
    orderLatest.onclick = () => loadInspectionPages({ order: null });
  };
  const renderRisk = (page) => {
    const records = page.records || [];
    const target = document.querySelector("#risk-list");
    target.replaceChildren();
    document.querySelector("#risk-empty").hidden = records.length !== 0;
    for (const record of records) {
      const item = document.createElement("li");
      const kind = record.kind || "audit";
      item.textContent = `${kind} · ${record.reason_code || "recorded"}`;
      target.appendChild(item);
    }
    const pageInfo = page.page || {};
    activeCursors.risk = pageInfo.before_sequence || null;
    riskPageStatus.textContent = pageInfo.before_sequence
      ? `Older outcomes before sequence ${pageInfo.before_sequence}.`
      : `Showing the latest ${records.length} risk outcomes.`;
    riskPageStatus.hidden = records.length === 0;
    riskLatest.hidden = !activeCursors.risk;
    riskOlder.hidden = !pageInfo.has_more;
    riskOlder.onclick = () => loadInspectionPages({ risk: pageInfo.next_before_sequence });
    riskLatest.onclick = () => loadInspectionPages({ risk: null });
  };

  const renderMembers = (page) => {
    const members = page.strategy_ids || [];
    const pageInfo = page.page || {};
    display("#members", members.length ? members.join(", ") : "No members on this page.");
    activeCursors.member = pageInfo.after_strategy_id || null;
    memberPageStatus.textContent = `Showing ${members.length} of ${pageInfo.total_count ?? 0} strategy members${activeCursors.member ? ` after ${activeCursors.member}` : " from the first members"}.`;
    memberPageStatus.hidden = false;
    memberLatest.hidden = !activeCursors.member;
    memberOlder.hidden = !pageInfo.has_more;
    memberOlder.onclick = () => loadInspectionPages({ member: pageInfo.next_after_strategy_id });
    memberLatest.onclick = () => loadInspectionPages({ member: null });
  };

  const renderReservations = (page) => {
    const rows = page.reservations || [];
    const target = document.querySelector("#reservations-table");
    target.replaceChildren();
    document.querySelector("#reservations-empty").hidden = rows.length !== 0;
    for (const reservation of rows) {
      const row = document.createElement("tr");
      cell(row, reservation.order_id);
      cell(row, reservation.strategy_id);
      cell(row, reservation.cash_usdt);
      cell(row, reservation.btc_quantity);
      cell(row, reservation.buy_quantity);
      target.appendChild(row);
    }
    const pageInfo = page.page || {};
    activeCursors.reservation = pageInfo.before_order_id || null;
    reservationPageStatus.textContent = `Showing ${rows.length} of ${pageInfo.total_count ?? 0} open reservations${activeCursors.reservation ? ` before ${activeCursors.reservation}` : " from the latest reservations"}.`;
    reservationPageStatus.hidden = false;
    reservationLatest.hidden = !activeCursors.reservation;
    reservationOlder.hidden = !pageInfo.has_more;
    reservationOlder.onclick = () => loadInspectionPages({ reservation: pageInfo.next_before_order_id });
    reservationLatest.onclick = () => loadInspectionPages({ reservation: null });
  };

  if (!portfolioId) {
    fail("Open /operator/<portfolio-id>/ to inspect a local portfolio.");
    return;
  }

  const endpoint = (resource) => `/v1/b4/portfolios/${encodeURIComponent(portfolioId)}/${resource}`;
  const inspectionEndpoint = `/v2/b4/portfolios/${encodeURIComponent(portfolioId)}/inspection`;
  const readInspection = (cursors) => {
    const query = new URLSearchParams({ risk_limit: "8", order_limit: "25", member_limit: "25", reservation_limit: "25" });
    if (cursors.risk) query.set("risk_before_sequence", cursors.risk);
    if (cursors.order) query.set("order_before_id", cursors.order);
    if (cursors.member) query.set("member_after_strategy_id", cursors.member);
    if (cursors.reservation) query.set("reservation_before_order_id", cursors.reservation);
    return fetch(`${inspectionEndpoint}?${query}`, {
      method: "GET",
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
    }).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Inspection failed (${response.status})`)));
  };
  const loadInspectionPages = (updates = {}) => readInspection({ ...activeCursors, ...updates })
    .then((inspection) => {
      renderMembers(inspection.members || {});
      renderReservations(inspection.reservations || {});
      renderOrders(inspection.orders || {});
      renderRisk(inspection.risk || {});
    })
    .catch((error) => fail(`Unable to inspect local portfolio: ${error.message}`));

  readInspection(activeCursors)
    .then((inspection) => {
      const { summary: payload, genesis, reservations, orders, risk } = inspection;
      display("#portfolio-id", payload.portfolio_id);
      display("#cash", payload.cash_usdt);
      display("#inventory", payload.btc_quantity);
      display("#mark", payload.mark_price);
      display("#events", payload.market_event_count ?? 0);
      display("#orders", payload.open_orders ?? 0);
      display("#lineage", genesis.fixture_lineage);
      display("#policy-fingerprint", genesis.policy_fingerprint);
      display("#portfolio-mode", genesis.shared_portfolio_id ? "SHARED" : "ISOLATED");
      display("#reserved-cash", reservations.cash_usdt);
      display("#reserved-btc", reservations.btc_quantity);
      display("#reserved-buy", reservations.buy_quantity);
      renderMembers(inspection.members || {});
      renderReservations(reservations || {});
      renderOrders(orders || {});
      renderRisk(risk || {});
      document.querySelector("#dashboard-link").href = `/v1/b4/portfolios/${encodeURIComponent(portfolioId)}/dashboard`;
      state.hidden = true;
      summary.hidden = false;
      workspace.hidden = false;
      actions.hidden = false;
    })
    .catch((error) => fail(`Unable to inspect local portfolio: ${error.message}`));
})();
