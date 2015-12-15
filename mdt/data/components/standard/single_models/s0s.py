from mdt.models.single import DMRISingleModelConfig

__author__ = 'Robbert Harms'
__date__ = "2015-06-22"
__maintainer__ = "Robbert Harms"
__email__ = "robbert.harms@maastrichtuniversity.nl"


class S0(DMRISingleModelConfig):

    name = 's0'
    description = 'Models the unweighted signal (aka. b0).'
    model_expression = 'S0'
