"""Passos reutilizados pelos testes do fluxo em navegador."""


def open_intake(test, page=None, plate="abc1d23", email="cliente@empresa.com.br", attendant="ANA"):
    page = page or test.page
    page.goto(test.url("/atendimentos/novo/"))
    page.select_option("#id_attendant", label=attendant)
    page.fill("#id_full_name", "Maria Souza")
    page.fill("#id_cpf", "52998224725")
    page.fill("#id_phone", "81990001712")
    if email:
        page.fill("#id_email", email)
    page.fill("#id_plate", plate)
    page.fill("#id_brand", "Fiat")
    page.fill("#id_model", "Argo")
    page.fill("#id_mileage", "45210")
    page.select_option("#id_mechanic", label="RUI")
    page.select_option("#id_origin", "instagram")
    test.submit(page=page)
    assert "/check-in/" in page.url, f"{page.url}: {page.inner_text('main')[:600]}"


def wait_saved(page):
    """Aguarda terminarem as gravações automáticas ainda em andamento."""
    expression = "![...document.querySelectorAll('[data-save-state]')].some(e => e.textContent === 'Salvando...')"
    for _ in range(300):
        if page.evaluate(expression):
            return
        page.wait_for_timeout(100)
    raise AssertionError("Gravações automáticas não terminaram")


def evaluate_all(page, bad_component=None, bad_tire=None, image=None):
    """Avalia tudo como OK, exceto o componente e o pneu indicados."""
    rows = page.locator(".check-row[data-check-item]")
    for index in range(rows.count()):
        row = rows.nth(index)
        name = row.locator(".check-row__name").inner_text()
        value = "SUBSTITUIR" if name == bad_component else "OK"
        row.locator(".evaluate label", has_text=value).first.click()
    tires = page.locator(".tire-card")
    for index in range(tires.count()):
        tire = tires.nth(index)
        name = tire.locator(".tire-card__title").inner_text()
        value = "SUBSTITUIR" if name == bad_tire else "OK"
        tire.locator(".evaluate label", has_text=value).first.click()
        tire.locator('[data-tire-field="psi"]').fill("32")
        if name == bad_tire:
            tire.locator("[data-photo-input]").set_input_files(image)
            tire.locator("[data-photo-thumb]").first.wait_for()
    wait_saved(page)


def advance_to_review(test, *, bad_component=None, page=None):
    """Percorre o fluxo pelo navegador até a revisão. Peça recomendada é recusada."""
    page = page or test.page
    upload_all_required(test, page)
    test.submit(page=page)
    evaluate_all(page, bad_component=bad_component)
    test.submit(page=page)
    if bad_component:
        test.submit(page.get_by_role("button", name="Cliente não autorizou"), page=page)
    test.submit("[data-step-submit]", page=page)
    upload_all_required(test, page)
    test.submit(page=page)
    assert "/revisao/" in page.url, page.url


def draw_signature(page):
    canvas = page.locator("[data-signature-canvas]")
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 60)
    page.mouse.down()
    for step in range(1, 12):
        page.mouse.move(box["x"] + 40 + step * 40, box["y"] + 60 + (step % 3) * 40)
    page.mouse.up()


def upload_all_required(test, page=None):
    page = page or test.page
    image = test.temp_image()
    slots = page.locator("[data-photo-slot][data-required]")
    for index in range(slots.count()):
        slot = slots.nth(index)
        slot.locator("[data-photo-input]").set_input_files(image)
        slot.locator("[data-photo-thumb]").first.wait_for()
