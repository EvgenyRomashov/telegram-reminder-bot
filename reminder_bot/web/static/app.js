const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";
const contactsNode = document.querySelector("#contacts");
const statusNode = document.querySelector("#status");
const dialog = document.querySelector("#contact-dialog");
const form = document.querySelector("#contact-form");

tg?.ready();
tg?.expand();

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData,
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let message = "Ошибка запроса";
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (_) {}
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value;
  return node.innerHTML;
}

function renderContacts(contacts) {
  if (!contacts.length) {
    contactsNode.innerHTML = `<div class="empty">Контактов пока нет.<br>Добавьте первый день рождения.</div>`;
    return;
  }
  contactsNode.innerHTML = contacts.map(contact => `
    <article class="contact" data-id="${contact.id}">
      <div><h2>${escapeHtml(contact.full_name)}</h2>
      <div class="meta">${contact.birth_date.split("-").reverse().join(".")} · ${escapeHtml(contact.contact_group)}</div></div>
      <div class="contact-actions">
        <button class="icon edit" aria-label="Редактировать">✎</button>
        <button class="icon delete" aria-label="Удалить">⌫</button>
      </div>
    </article>`).join("");
  document.querySelectorAll(".edit").forEach(button => button.addEventListener("click", editContact));
  document.querySelectorAll(".delete").forEach(button => button.addEventListener("click", removeContact));
}

async function loadContacts() {
  if (!initData) {
    statusNode.textContent = "Откройте приложение из Telegram-бота.";
    return;
  }
  try {
    const contacts = await api("/api/contacts");
    window.currentContacts = contacts;
    renderContacts(contacts);
    statusNode.hidden = true;
  } catch (error) {
    statusNode.textContent = error.message;
  }
}

function openForm(contact = null) {
  document.querySelector("#form-title").textContent = contact ? "Редактировать" : "Новый контакт";
  document.querySelector("#contact-id").value = contact?.id || "";
  document.querySelector("#full-name").value = contact?.full_name || "";
  document.querySelector("#birth-date").value = contact?.birth_date || "";
  document.querySelector("#contact-group").value = contact?.contact_group || "Друзья";
  document.querySelector("#form-error").textContent = "";
  dialog.showModal();
}

function editContact(event) {
  const id = Number(event.target.closest(".contact").dataset.id);
  openForm(window.currentContacts.find(contact => contact.id === id));
}

async function removeContact(event) {
  const id = Number(event.target.closest(".contact").dataset.id);
  const contact = window.currentContacts.find(item => item.id === id);
  if (!confirm(`Удалить «${contact.full_name}»?`)) return;
  try { await api(`/api/contacts/${id}`, { method: "DELETE" }); await loadContacts(); }
  catch (error) { alert(error.message); }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const id = document.querySelector("#contact-id").value;
  const payload = {
    full_name: document.querySelector("#full-name").value,
    birth_date: document.querySelector("#birth-date").value,
    contact_group: document.querySelector("#contact-group").value,
  };
  try {
    await api(id ? `/api/contacts/${id}` : "/api/contacts", {
      method: id ? "PUT" : "POST", body: JSON.stringify(payload),
    });
    dialog.close();
    await loadContacts();
    tg?.HapticFeedback?.notificationOccurred("success");
  } catch (error) {
    document.querySelector("#form-error").textContent = error.message;
  }
});

document.querySelector("#add-button").addEventListener("click", () => openForm());
document.querySelector("#close-button").addEventListener("click", () => dialog.close());
document.querySelector("#cancel-button").addEventListener("click", () => dialog.close());
loadContacts();
