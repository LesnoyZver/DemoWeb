(function () {
  "use strict";

  var STORAGE_KEY = "cart_v1";
  var PENDING_KEY = "order_pending";
  var MAX_QTY = 99;
  var MAX_IMAGE_BYTES = 3 * 1024 * 1024;
  var ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

  var priceFormatter = new Intl.NumberFormat("ru-RU");

  function formatPrice(value) {
    return priceFormatter.format(Number(value) || 0) + "\u00a0BYN";
  }

  function readCart() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      var data = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(data)) return [];
      return data
        .filter(function (item) {
          return item && Number(item.id) > 0 && Number(item.qty) > 0;
        })
        .map(function (item) {
          var qty = parseInt(item.qty, 10) || 1;
          return {
            id: Number(item.id),
            qty: Math.min(MAX_QTY, Math.max(1, qty)),
            name: String(item.name || ""),
            price: Number(item.price) || 0,
            image: String(item.image || ""),
            slug: String(item.slug || ""),
          };
        });
    } catch (error) {
      return [];
    }
  }

  function writeCart(cart) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(cart));
    } catch (error) {
      /* хранилище недоступно — корзина проживёт до перезагрузки */
    }
    updateCartCount();
  }

  function cartQuantity(cart) {
    return cart.reduce(function (sum, item) {
      return sum + item.qty;
    }, 0);
  }

  function updateCartCount() {
    var count = cartQuantity(readCart());
    document.querySelectorAll("[data-cart-count]").forEach(function (el) {
      if (count > 0) {
        el.textContent = String(count);
        el.hidden = false;
      } else {
        el.hidden = true;
      }
    });
  }

  function addToCart(product) {
    var cart = readCart();
    var existing = cart.find(function (item) {
      return item.id === product.id;
    });
    if (existing) {
      existing.qty = Math.min(MAX_QTY, existing.qty + 1);
    } else {
      cart.push({
        id: product.id,
        qty: 1,
        name: product.name,
        price: product.price,
        image: product.image,
        slug: product.slug,
      });
    }
    writeCart(cart);
  }

  /* -------------------------------------------------- добавление */

  document.querySelectorAll("[data-add-to-cart]").forEach(function (button) {
    button.addEventListener("click", function () {
      addToCart({
        id: Number(button.dataset.id),
        name: button.dataset.name || "",
        price: Number(button.dataset.price) || 0,
        image: button.dataset.image || "",
        slug: button.dataset.slug || "",
      });

      var original = button.textContent;
      button.textContent = "Добавлено";
      window.setTimeout(function () {
        button.textContent = original;
      }, 1200);
    });
  });

  /* ------------------------------------------------------ корзина */

  function makeElement(tag, className, text) {
    var el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function makeItemMedia(item) {
    var media = makeElement("div", "cart-item__media");
    if (item.image) {
      var img = document.createElement("img");
      img.src = item.image;
      img.alt = item.name;
      media.appendChild(img);
    } else {
      media.appendChild(makeElement("div", "product-card__placeholder"));
    }
    return media;
  }

  function renderCartPage(root) {
    var cart = readCart();
    root.textContent = "";

    if (!cart.length) {
      var empty = makeElement("div", "cart-empty");
      empty.appendChild(makeElement("p", null, "Корзина пуста."));
      var emptyLink = makeElement("a", "btn btn-primary", "Смотреть каталог");
      emptyLink.href = "/catalog";
      empty.appendChild(emptyLink);
      root.appendChild(empty);
      return;
    }

    var list = makeElement("ul", "cart-list");

    cart.forEach(function (item) {
      var row = makeElement("li", "cart-item");
      row.appendChild(makeItemMedia(item));

      var body = makeElement("div", "cart-item__body");
      var name = makeElement("h2", "cart-item__name");
      var link = makeElement("a", null, item.name);
      link.href = "/product/" + item.slug;
      name.appendChild(link);
      body.appendChild(name);
      body.appendChild(makeElement("p", "cart-item__price", formatPrice(item.price)));
      row.appendChild(body);

      var side = makeElement("div", "cart-item__side");

      var control = makeElement("div", "qty-control");
      var minus = makeElement("button", "qty-btn", "−");
      minus.type = "button";
      minus.setAttribute("aria-label", "Уменьшить количество");
      var input = document.createElement("input");
      input.className = "qty-input";
      input.type = "number";
      input.min = "1";
      input.max = String(MAX_QTY);
      input.value = String(item.qty);
      input.setAttribute("aria-label", "Количество");
      var plus = makeElement("button", "qty-btn", "+");
      plus.type = "button";
      plus.setAttribute("aria-label", "Увеличить количество");

      minus.addEventListener("click", function () {
        updateQty(item.id, item.qty - 1);
      });
      plus.addEventListener("click", function () {
        updateQty(item.id, item.qty + 1);
      });
      input.addEventListener("change", function () {
        updateQty(item.id, parseInt(input.value, 10));
      });

      control.appendChild(minus);
      control.appendChild(input);
      control.appendChild(plus);
      side.appendChild(control);

      side.appendChild(
        makeElement("span", "cart-item__sum", formatPrice(item.price * item.qty))
      );

      var remove = makeElement("button", "cart-item__remove", "Удалить");
      remove.type = "button";
      remove.addEventListener("click", function () {
        writeCart(
          readCart().filter(function (entry) {
            return entry.id !== item.id;
          })
        );
        renderCartPage(root);
      });
      side.appendChild(remove);

      row.appendChild(side);
      list.appendChild(row);
    });

    root.appendChild(list);

    var total = cart.reduce(function (sum, item) {
      return sum + item.price * item.qty;
    }, 0);

    var footer = makeElement("div", "cart-footer");
    var totalEl = makeElement("div", "cart-total");
    totalEl.appendChild(makeElement("span", null, "Итого"));
    totalEl.appendChild(document.createTextNode(formatPrice(total)));
    footer.appendChild(totalEl);

    var actions = makeElement("div", "cart-actions");
    var continueLink = makeElement("a", "text-link", "Продолжить покупки");
    continueLink.href = "/catalog";
    var checkoutLink = makeElement("a", "btn btn-primary", "Оформить заказ");
    checkoutLink.href = "/checkout";
    actions.appendChild(continueLink);
    actions.appendChild(checkoutLink);
    footer.appendChild(actions);

    root.appendChild(footer);
  }

  function updateQty(id, qty) {
    var cart = readCart();
    var item = cart.find(function (entry) {
      return entry.id === id;
    });
    if (!item) return;
    if (!Number.isFinite(qty)) qty = 1;
    item.qty = Math.min(MAX_QTY, Math.max(1, Math.floor(qty)));
    writeCart(cart);
    var root = document.querySelector("[data-cart-page]");
    if (root) renderCartPage(root);
  }

  var cartRoot = document.querySelector("[data-cart-page]");
  if (cartRoot) renderCartPage(cartRoot);

  /* ------------------------------------------------- оформление */

  var checkoutForm = document.querySelector("[data-checkout-form]");
  if (checkoutForm) {
    sessionStorage.removeItem(PENDING_KEY);
  }

  function renderCheckoutSummary(cart) {
    var summary = document.querySelector("[data-checkout-summary]");
    var totalEl = document.getElementById("checkout-total");
    var itemsInput = document.getElementById("checkout-items");
    if (!summary || !totalEl || !itemsInput) return;

    summary.textContent = "";
    itemsInput.value = JSON.stringify(
      cart.map(function (item) {
        return { id: item.id, qty: item.qty };
      })
    );

    if (!cart.length) {
      summary.appendChild(makeElement("p", "empty-note", "Корзина пуста."));
      totalEl.textContent = formatPrice(0);
      return;
    }

    var list = makeElement("div", "summary-list");
    cart.forEach(function (item) {
      var row = makeElement("div", "summary-item");
      row.appendChild(makeElement("span", null, item.name + " × " + item.qty));
      row.appendChild(makeElement("span", null, formatPrice(item.price * item.qty)));
      list.appendChild(row);
    });
    summary.appendChild(list);

    totalEl.textContent = formatPrice(
      cart.reduce(function (sum, item) {
        return sum + item.price * item.qty;
      }, 0)
    );
  }

  if (checkoutForm) {
    var initialCart = readCart();
    renderCheckoutSummary(initialCart);

    var submitButton = checkoutForm.querySelector('button[type="submit"]');
    if (!initialCart.length && submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Корзина пуста";
    }

    checkoutForm.addEventListener("submit", function (event) {
      var cart = readCart();
      renderCheckoutSummary(cart);

      if (!cart.length) {
        event.preventDefault();
        return;
      }

      var valid = true;
      var name = checkoutForm.elements.customer_name;
      var phone = checkoutForm.elements.phone;
      var email = checkoutForm.elements.email;
      var address = checkoutForm.elements.address;

      function showError(field, message) {
        clearError(field);
        var span = makeElement("span", "field-error", message);
        field.parentNode.appendChild(span);
        valid = false;
      }

      function clearError(field) {
        var existing = field.parentNode.querySelector(".field-error");
        if (existing) existing.remove();
      }

      clearError(name);
      clearError(phone);
      clearError(email);
      clearError(address);

      if (name.value.trim().length < 2) {
        showError(name, "Укажите имя (минимум 2 символа).");
      }
      var digits = (phone.value.match(/\d/g) || []).length;
      if (digits < 7 || !/^[0-9+()\-\s]+$/.test(phone.value.trim())) {
        showError(phone, "Укажите корректный номер телефона.");
      }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.value.trim())) {
        showError(email, "Укажите корректный e-mail.");
      }
      if (address.value.trim().length < 5) {
        showError(address, "Укажите адрес доставки.");
      }

      if (!valid) {
        event.preventDefault();
        var firstError = checkoutForm.querySelector(".field-error");
        if (firstError) {
          var field = firstError.parentNode.querySelector("input, textarea, select");
          if (field) field.focus();
        }
        return;
      }

      sessionStorage.setItem(PENDING_KEY, "1");
    });
  }

  /* ------------------------------------------- очистка после заказа */

  var page = document.body.getAttribute("data-page");
  if (page === "order-success") {
    if (sessionStorage.getItem(PENDING_KEY) === "1") {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (error) {
        /* ignore */
      }
      sessionStorage.removeItem(PENDING_KEY);
    }
  } else {
    sessionStorage.removeItem(PENDING_KEY);
  }

  /* --------------------------------------- предпросмотр изображения */

  var imageInput = document.querySelector("[data-image-input]");
  if (imageInput) {
    var preview = document.querySelector("[data-image-preview]");
    var previewPlaceholder = document.querySelector("[data-image-placeholder]");
    var imageError = document.querySelector("[data-image-error]");

    imageInput.addEventListener("change", function () {
      if (imageError) {
        imageError.hidden = true;
        imageError.textContent = "";
      }

      var file = imageInput.files && imageInput.files[0];
      if (!file) return;

      var extensionOk = /\.(jpe?g|png|webp)$/i.test(file.name);
      var typeOk = file.type
        ? ALLOWED_IMAGE_TYPES.indexOf(file.type) !== -1
        : extensionOk;

      if (!typeOk) {
        if (imageError) {
          imageError.textContent = "Допустимы только изображения JPG, PNG или WEBP.";
          imageError.hidden = false;
        }
        imageInput.value = "";
        return;
      }

      if (file.size > MAX_IMAGE_BYTES) {
        if (imageError) {
          imageError.textContent = "Файл больше 3 МБ.";
          imageError.hidden = false;
        }
        imageInput.value = "";
        return;
      }

      if (preview) {
        var objectUrl = URL.createObjectURL(file);
        preview.src = objectUrl;
        preview.hidden = false;
        preview.onload = function () {
          URL.revokeObjectURL(objectUrl);
        };
      }
      if (previewPlaceholder) previewPlaceholder.hidden = true;
    });
  }

  updateCartCount();
})();
