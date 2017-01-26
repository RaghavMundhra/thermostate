"""
Base ThermoState module
"""
from itertools import permutations
from math import isclose

from CoolProp.CoolProp import PropsSI, PhaseSI
import CoolProp
from pint import UnitRegistry
from pint.unit import UnitsContainer, UnitDefinition
from pint.converters import ScaleConverter

units = UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = units.Quantity
units.define(UnitDefinition('percent', 'pct', (), ScaleConverter(1.0/100.0)))


def munge_coolprop_input_prop(prop):
    prop = prop.replace('_INPUTS', '').replace('mass', '').replace('D', 'V')
    return prop.replace('Q', 'X').lower().replace('t', 'T')


def isclose_quant(a, b, *args, **kwargs):
    return isclose(a.magnitude, b.magnitude, *args, **kwargs)


class StateError(Exception):
    pass


class State(object):
    """Basic State manager for thermodyanmic states

    Parameters
    ----------
    substance : `str`
        One of the substances supported by CoolProp
    T : `pint.UnitRegistry.Quantity`
        Temperature
    p : `pint.UnitRegistry.Quantity`
        Pressure
    u : `pint.UnitRegistry.Quantity`
        Mass-specific internal energy
    s : `pint.UnitRegistry.Quantity`
        Mass-specific entropy
    v : `pint.UnitRegistry.Quantity`
        Mass-specific volume
    h : `pint.UnitRegistry.Quantity`
        Mass-specific enthalpy
    x : `pint.UnitRegistry.Quantity`
        Quality
    """
    allowed_subs = ['AIR', 'AMMONIA', 'WATER', 'PROPANE', 'R134A', 'R22', 'ISOBUTANE']

    CP_allowed_pairs = [munge_coolprop_input_prop(k) for k in dir(CoolProp.constants)
                        if 'INPUTS' in k and 'molar' not in k]
    CP_allowed_pairs.extend([k[::-1] for k in CP_allowed_pairs])

    CP_unsupported_pairs = ['Tu', 'Th', 'us']
    CP_unsupported_pairs.extend([k[::-1] for k in CP_unsupported_pairs])

    all_props = list('Tpvuhsx')

    all_pairs = [''.join(a) for a in permutations(all_props, 2)]

    other_props = ['cp', 'cv']

    dimensions = {
        'T': UnitsContainer({'[temperature]': 1.0}),
        'p': UnitsContainer({'[mass]': 1.0, '[length]': -1.0, '[time]': -2.0}),
        'v': UnitsContainer({'[length]': 3.0, '[mass]': -1.0}),
        'u': UnitsContainer({'[length]': 2.0, '[time]': -2.0}),
        'h': UnitsContainer({'[length]': 2.0, '[time]': -2.0}),
        's': UnitsContainer({'[length]': 2.0, '[time]': -2.0, '[temperature]': -1.0}),
        'x': UnitsContainer({}),
    }

    SI_units = {
        'T': 'kelvin',
        'p': 'pascal',
        'v': 'meter**3/kilogram',
        'u': 'joules/kilogram',
        'h': 'joules/kilogram',
        's': 'joules/(kilogram*kelvin)',
        'x': 'dimensionless',
        'cp': 'joules/(kilogram*kelvin)',
        'cv': 'joules/(kilogram*kelvin)',
    }

    def __setattr__(self, key, value):
        if key in self.CP_allowed_pairs and key not in self.CP_unsupported_pairs:
            self._check_dimensions(key, value)
            self._set_properties(key, value)
        elif key in self.CP_unsupported_pairs:
            raise StateError("The pair of input properties entered ({}) isn't supported yet. "
                             "Sorry!".format(key))
        elif key.startswith('_') or key == 'sub':
            object.__setattr__(self, key, value)
        else:
            raise AttributeError('The pair of properties entered is not one of the allowed pairs '
                                 'of properties. Perhaps one of the letters was capitalized '
                                 'improperly?\nThe pair of properties was "{}".'.format(key))

    def __getattr__(self, key):
        if key in self.all_props:
            return object.__getattribute__(self, '_' + key)
        elif key in self.CP_allowed_pairs:
            val_0 = object.__getattribute__(self, '_' + key[0])
            val_1 = object.__getattribute__(self, '_' + key[1])
            return val_0, val_1
        elif key == 'phase':
            return object.__getattribute__(self, '_' + key)
        elif key in self.other_props:
            return object.__getattribute__(self, '_' + key)
        else:
            raise AttributeError("Property unknown")

    def __eq__(self, other):
        """Use any two independent and intensive properties to
        test for equality. Choose T and v because the EOS tends
        to be defined in terms of T and density.
        """
        if isclose_quant(other.T, self.T) and isclose_quant(other.v, self.v):
            return True

    def __le__(self, other):
        return NotImplemented

    def __lt__(self, other):
        return NotImplemented

    def __gt__(self, other):
        return NotImplemented

    def __ge__(self, other):
        return NotImplemented

    def __init__(self, substance, **kwargs):
        if substance.upper() in self.allowed_subs:
            self.sub = substance.upper()
        else:
            raise ValueError('{} is not an allowed substance. Choose one of {}.'.format(
                substance, self.allowed_subs,
            ))

        input_props = ''
        for arg in kwargs:
            if arg not in self.all_props:
                raise ValueError('The argument {} is not allowed.'.format(arg))
            else:
                input_props += arg

        if len(input_props) > 2 or len(input_props) == 1:
            raise ValueError('Incorrect number of properties specified. Must be 2 or 0.')

        if len(input_props) > 0 and input_props not in self.allowed_pairs:
            raise ValueError('The supplied pair of properties, {props[0]} and {props[1]} is not an '
                             'implemented set of independent properties.'.format(props=input_props))

        if len(input_props) > 0:
            setattr(self, input_props, (kwargs[input_props[0]], kwargs[input_props[1]]))

    def to_SI(self, prop, value):
        return value.to(self.SI_units[prop])

    def to_PropsSI(self, prop, value):
        return self.to_SI(prop, value).magnitude

    def _check_dimensions(self, properties, value):
        if value[0].dimensionality != self.dimensions[properties[0]]:
            raise StateError('The dimensions for {props[0]} must be {dim}'.format(
                props=properties,
                dim=self.dimensions[properties[0]]))
        elif value[1].dimensionality != self.dimensions[properties[1]]:
            raise StateError('The dimensions for {props[1]} must be {dim}'.format(
                props=properties,
                dim=self.dimensions[properties[1]]))

    def _set_properties(self, known_props, known_values):
        if len(known_props) != 2 or len(known_values) != 2 or len(known_props) != len(known_values):
            raise StateError('Only specify two properties to _set_properties')

        props = []
        vals = []

        if known_props == 'Tp' or known_props == 'pT':
            try:
                PropsSI('Phase',
                        known_props[0].upper(), self.to_PropsSI(known_props[0], known_values[0]),
                        known_props[1].upper(), self.to_PropsSI(known_props[1], known_values[1]),
                        self.sub)
            except ValueError as e:
                if 'Saturation pressure' in str(e):
                    raise StateError('The given values for T and p are not independent.')
                else:
                    raise

        for prop, val in zip(known_props, known_values):
            if prop == 'x':
                props.append('Q')
                vals.append(self.to_PropsSI('x', val))
            elif prop == 'v':
                props.append('DMASS')
                vals.append(1.0/self.to_PropsSI('v', val))
            else:
                postfix = '' if prop in 'Tp' else 'MASS'
                props.append(prop.upper() + postfix)
                vals.append(self.to_PropsSI(prop, val))

            setattr(self, '_' + prop, self.to_SI(prop, val))

        # unknown_props has to be a copy of the all_props list here,
        # otherwise, properties get permanently removed
        unknown_props = self.all_props[:]
        unknown_props.remove(known_props[0])
        unknown_props.remove(known_props[1])
        unknown_props += self.other_props

        for prop in unknown_props:
            if prop == 'v':
                value = Q_(1.0/PropsSI('DMASS', props[0], vals[0], props[1], vals[1], self.sub),
                           self.SI_units[prop])
            elif prop == 'x':
                value = Q_(PropsSI('Q', props[0], vals[0], props[1], vals[1], self.sub),
                           self.SI_units[prop])
                if value == -1.0:
                    value = None
            else:
                postfix = '' if prop in 'Tp' else 'MASS'
                p = prop.upper() + postfix
                value = Q_(PropsSI(p, props[0], vals[0], props[1], vals[1], self.sub),
                           self.SI_units[prop])

            setattr(self, '_' + prop, value)

        self._phase = PhaseSI(props[0], vals[0], props[1], vals[1], self.sub)
