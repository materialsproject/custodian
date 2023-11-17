import os

from custodian import TEST_FILES
from custodian.lobster.handlers import ChargeSpillingValidator, EnoughBandsValidator, LobsterFilesValidator

test_files_lobster = f"{TEST_FILES}/lobster/lobsterouts"


class TestChargeSpillingValidator:
    def test_check_and_correct(self):
        v = ChargeSpillingValidator(output_filename=f"{test_files_lobster}/lobsterout.normal")
        assert not v.check()

        v2 = ChargeSpillingValidator(output_filename=f"{test_files_lobster}/lobsterout.largespilling")
        assert v2.check()

        v2b = ChargeSpillingValidator(output_filename=f"{test_files_lobster}/lobsterout.largespilling_2")
        assert v2b.check()

        v3 = ChargeSpillingValidator(output_filename=f"{test_files_lobster}/nolobsterout/lobsterout")
        assert not v3.check()

        v4 = ChargeSpillingValidator(output_filename=f"{test_files_lobster}/no_spin/lobsterout")
        assert not v4.check()

    def test_as_dict(self):
        v = ChargeSpillingValidator(output_filename=f"{test_files_lobster}/lobsterout.normal")
        dct = v.as_dict()
        v2 = ChargeSpillingValidator.from_dict(dct)
        assert isinstance(v2, ChargeSpillingValidator)


class TestLobsterFilesValidator:
    def test_check_and_correct_1(self):
        os.chdir(test_files_lobster)
        v = LobsterFilesValidator()
        assert not v.check()

    def test_check_and_correct_2(self):
        os.chdir(f"{test_files_lobster}/../lobsterins")
        v2 = LobsterFilesValidator()
        assert v2.check()

    def test_check_and_correct_3(self):
        os.chdir(f"{test_files_lobster}/crash")
        v3 = LobsterFilesValidator()
        assert v3.check()

    def test_as_dict(self):
        os.chdir(test_files_lobster)
        v = LobsterFilesValidator()
        dct = v.as_dict()
        v2 = LobsterFilesValidator.from_dict(dct)
        assert isinstance(v2, LobsterFilesValidator)


class TestEnoughBandsValidator:
    def test_check_and_correct(self):
        v = EnoughBandsValidator(output_filename=f"{test_files_lobster}/lobsterout.normal")
        assert not v.check()

    def test_check_and_correct2(self):
        v2 = EnoughBandsValidator(output_filename=f"{test_files_lobster}/lobsterout.nocohp")
        assert v2.check()

    def test_check_and_correct3(self):
        v3 = EnoughBandsValidator(output_filename=f"{test_files_lobster}/nolobsterout/lobsterout")
        assert not v3.check()

    def test_as_dict(self):
        v = EnoughBandsValidator(output_filename=f"{test_files_lobster}/lobsterout.normal")
        dct = v.as_dict()
        v2 = EnoughBandsValidator.from_dict(dct)
        assert isinstance(v2, EnoughBandsValidator)
