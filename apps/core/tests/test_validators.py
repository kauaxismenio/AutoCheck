"""Testes das regras de validação (Python puro, rodam com ou sem Django)."""
import unittest

from apps.core.validators import documents, email, phone, plate


class CPFTests(unittest.TestCase):
    def test_valid_cpf_with_and_without_mask(self):
        self.assertTrue(documents.is_valid_cpf("529.982.247-25"))
        self.assertTrue(documents.is_valid_cpf("52998224725"))

    def test_invalid_check_digits(self):
        self.assertFalse(documents.is_valid_cpf("529.982.247-24"))
        self.assertFalse(documents.is_valid_cpf("123.456.789-00"))

    def test_repeated_digits_rejected(self):
        for d in "0123456789":
            self.assertFalse(documents.is_valid_cpf(d * 11))

    def test_wrong_length(self):
        self.assertFalse(documents.is_valid_cpf("5299822472"))
        self.assertFalse(documents.is_valid_cpf(""))
        self.assertFalse(documents.is_valid_cpf(None))

    def test_format(self):
        self.assertEqual(documents.format_cpf("52998224725"), "529.982.247-25")


class CNPJTests(unittest.TestCase):
    def test_traditional_numeric_cnpj(self):
        self.assertTrue(documents.is_valid_cnpj("11.222.333/0001-81"))
        self.assertTrue(documents.is_valid_cnpj("00.000.000/0001-91"))  # Banco do Brasil
        self.assertTrue(documents.is_valid_cnpj("33000167000101"))      # Petrobras

    def test_official_alphanumeric_example(self):
        # Exemplo do FAQ oficial da Receita Federal: 12.ABC.345/01DE-35
        self.assertEqual(documents.calculate_cnpj_check_digits("12ABC34501DE"), "35")
        self.assertTrue(documents.is_valid_cnpj("12.ABC.345/01DE-35"))
        self.assertTrue(documents.is_alphanumeric_cnpj("12.ABC.345/01DE-35"))

    def test_lowercase_is_normalized(self):
        self.assertTrue(documents.is_valid_cnpj("12.abc.345/01de-35"))
        self.assertEqual(documents.normalize_cnpj("12.abc.345/01de-35"), "12ABC34501DE35")

    def test_invalid_check_digits(self):
        self.assertFalse(documents.is_valid_cnpj("12.ABC.345/01DE-36"))
        self.assertFalse(documents.is_valid_cnpj("11.222.333/0001-82"))

    def test_letters_not_allowed_in_check_digits(self):
        self.assertFalse(documents.is_valid_cnpj("12ABC34501DE3A"))

    def test_invalid_characters_rejected_not_stripped(self):
        self.assertFalse(documents.is_valid_cnpj("12ABC34501D@35"))
        self.assertFalse(documents.is_valid_cnpj("12ÁBC34501DE35"))

    def test_repeated_and_length(self):
        self.assertFalse(documents.is_valid_cnpj("00000000000000"))
        self.assertFalse(documents.is_valid_cnpj("1122233300018"))
        self.assertFalse(documents.is_valid_cnpj(""))

    def test_numeric_rule_matches_ascii_rule(self):
        # Para CNPJ numérico, ASCII−48 produz exatamente o valor do dígito.
        self.assertEqual(documents.calculate_cnpj_check_digits("112223330001"), "81")

    def test_format(self):
        self.assertEqual(documents.format_cnpj("12abc34501de35"), "12.ABC.345/01DE-35")


class PhoneTests(unittest.TestCase):
    def test_mobile(self):
        self.assertEqual(phone.phone_type("(81) 9 9000-1712"), phone.MOBILE)
        self.assertEqual(phone.format_phone("81990001712"), "(81) 9 9000-1712")

    def test_landline(self):
        self.assertEqual(phone.phone_type("8134567890"), phone.LANDLINE)
        self.assertEqual(phone.format_phone("8134567890"), "(81) 3456-7890")

    def test_country_code_and_trunk_prefix(self):
        self.assertEqual(phone.normalize_phone("+55 81 99000-1712"), "81990001712")
        self.assertEqual(phone.normalize_phone("0 81 3456-7890"), "8134567890")

    def test_invalid(self):
        self.assertFalse(phone.is_valid_phone("81 8603-17121"))   # 9 dígitos sem iniciar com 9
        self.assertFalse(phone.is_valid_phone("8190001712"))       # 8 dígitos começando com 9
        self.assertFalse(phone.is_valid_phone("01990001712"))      # DDD com zero
        self.assertFalse(phone.is_valid_phone("990001712"))        # sem DDD
        self.assertFalse(phone.is_valid_phone(""))


class PlateTests(unittest.TestCase):
    def test_old_format(self):
        self.assertEqual(plate.plate_type("abc-1234"), plate.OLD)
        self.assertEqual(plate.format_plate("abc1234"), "ABC-1234")

    def test_mercosul(self):
        self.assertEqual(plate.plate_type("abc1d23"), plate.MERCOSUL)
        self.assertEqual(plate.format_plate(" ABC-1D23 "), "ABC1D23")

    def test_invalid(self):
        for value in ("AB1234", "ABCD123", "ABC12D3", "1BC1234", ""):
            self.assertFalse(plate.is_valid_plate(value), value)


class EmailTests(unittest.TestCase):
    def test_business_domains_allowed(self):
        for value in ("joao@oficina.com.br", "contato@empresa.ind.br", "a.b+c@sub.dominio.io"):
            self.assertTrue(email.is_valid_email(value), value)

    def test_domain_is_lowercased(self):
        self.assertEqual(email.normalize_email(" Joao@Oficina.COM.BR "), "Joao@oficina.com.br")

    def test_invalid(self):
        for value in ("joao@", "@x.com", "joao@localhost", "joao@-x.com", "joao@x.c",
                      "jo..ao@x.com", "joao@x..com", "joao@@x.com", "joao@x.123"):
            self.assertFalse(email.is_valid_email(value), value)

    def test_idn_domain(self):
        self.assertTrue(email.is_valid_email("contato@açaí.com.br"))


if __name__ == "__main__":
    unittest.main()
