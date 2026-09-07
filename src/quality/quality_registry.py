QUALITY_REGISTRY={
    "RD001":{
        "name":"Road Overshoot","layer":"roads",
        "quality_element":"Logical Consistency","sub_element":"Topological Consistency",
        "evaluation_method":"direct_automated","measure":"overshoot_count",
        "threshold":0,"threshold_source":"meyaar","revalidation_rule":"RD001"
    },
    "RD002":{
        "name":"Road Undershoot","layer":"roads",
        "quality_element":"Logical Consistency","sub_element":"Topological Consistency",
        "evaluation_method":"direct_automated","measure":"undershoot_count",
        "threshold":0,"threshold_source":"meyaar","revalidation_rule":"RD002"
    },
    "RD003":{
        "name":"Duplicate Roads","layer":"roads",
        "quality_element":"Logical Consistency","sub_element":"Duplicate Feature Consistency",
        "evaluation_method":"direct_automated","measure":"duplicate_road_count",
        "threshold":0,"threshold_source":"meyaar","revalidation_rule":"RD003"
    },
    "RD004":{
        "name":"Invalid Geometry","layer":"roads",
        "quality_element":"Logical Consistency","sub_element":"Geometry Validity",
        "evaluation_method":"direct_automated","measure":"invalid_geometry_count",
        "threshold":0,"threshold_source":"meyaar","revalidation_rule":"RD004"
    },
    "RD005":{
        "name":"Missing Geometry","layer":"roads",
        "quality_element":"Completeness","sub_element":"Geometry Completeness",
        "evaluation_method":"direct_automated","measure":"geometry_completeness",
        "threshold":95,"threshold_source":"geosa_proxy","revalidation_rule":"RD005",
        "note":"Geometry presence is used as a proxy measure. It does not establish full real-world dataset completeness."
    },
    "BLD001":{
        "name":"Building Overlap","layer":"buildings",
        "quality_element":"Logical Consistency","sub_element":"Topological Consistency",
        "evaluation_method":"direct_automated","measure":"building_overlap_count",
        "threshold":0,"threshold_source":"meyaar","revalidation_rule":"BLD001"
    },
    "BLD002":{
        "name":"Duplicate Buildings","layer":"buildings",
        "quality_element":"Logical Consistency","sub_element":"Duplicate Feature Consistency",
        "evaluation_method":"direct_automated","measure":"duplicate_building_count",
        "threshold":0,"threshold_source":"meyaar","revalidation_rule":"BLD002"
    },
    "BLD003":{
        "name":"Invalid Geometry","layer":"buildings",
        "quality_element":"Logical Consistency","sub_element":"Geometry Validity",
        "evaluation_method":"direct_automated","measure":"invalid_geometry_count",
        "threshold":0,"threshold_source":"meyaar","revalidation_rule":"BLD003"
    },
    "BLD004":{
        "name":"Missing Geometry","layer":"buildings",
        "quality_element":"Completeness","sub_element":"Geometry Completeness",
        "evaluation_method":"direct_automated","measure":"geometry_completeness",
        "threshold":95,"threshold_source":"geosa_proxy","revalidation_rule":"BLD004",
        "note":"Geometry presence is used as a proxy measure. It does not establish full real-world dataset completeness."
    },
    "GIS001":{
        "name":"Internal CRS Check","layer":"general",
        "quality_element":"Logical Consistency","sub_element":"Reference System Conformance",
        "evaluation_method":"direct_automated","measure":"internal_crs_valid",
        "threshold":None,"threshold_source":"meyaar","revalidation_rule":"GIS001",
        "note":"EPSG:4326 is Meyaar's internal processing CRS, not a GeoSA compliance threshold."
    },
    "GIS002":{
        "name":"Invalid Coordinates","layer":"general",
        "quality_element":"Logical Consistency","sub_element":"Coordinate Domain Consistency",
        "evaluation_method":"direct_automated","measure":"invalid_coordinate_count",
        "threshold":0,"threshold_source":"meyaar","revalidation_rule":"GIS002"
    },
    "GIS003":{
        "name":"Missing Required Attributes","layer":"general",
        "quality_element":"Completeness","sub_element":"Attribute Completeness",
        "evaluation_method":"direct_automated","measure":"missing_required_attribute_count",
        "threshold":0,"threshold_source":"dataset_specification","revalidation_rule":"GIS003"
    },
    "GIS004":{
        "name":"Wrong Data Type","layer":"general",
        "quality_element":"Logical Consistency","sub_element":"Schema Conformance",
        "evaluation_method":"direct_automated","measure":"wrong_data_type_count",
        "threshold":0,"threshold_source":"dataset_specification","revalidation_rule":"GIS004"
    },
    "GIS005":{
        "name":"Invalid Attribute Values","layer":"general",
        "quality_element":"Logical Consistency","sub_element":"Domain Conformance",
        "evaluation_method":"direct_automated","measure":"invalid_attribute_value_count",
        "threshold":0,"threshold_source":"dataset_specification","revalidation_rule":"GIS005"
    }
}

def get_quality_definition(rule_id:str)->dict|None:
    return QUALITY_REGISTRY.get(rule_id)

def get_applicable_quality_definitions(layer_name:str)->dict[str,dict]:
    if layer_name not in {"roads","buildings"}:
        raise ValueError("layer_name must be roads or buildings.")
    return {
        rule_id:definition
        for rule_id,definition in QUALITY_REGISTRY.items()
        if definition["layer"] in {layer_name,"general"}
    }
