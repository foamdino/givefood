# coding: utf-8
from givefood.func import is_uk, parse_tesco_order_text

def test_is_uk():
    result = is_uk("49.674,-14.015517")
    assert result

# TODO fix broken £ unicode encoding
# def test_parse_tesco_order_text():
#     order_text = "# 10 Tesco Sliced Carrots In Water 300G £0.30 £3.00"
#     result = parse_tesco_order_text(order_text)
#     assert result == []
