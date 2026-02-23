//adapted from https://github.com/zachleat/github-issue-to-json-file/blob/main/parse-issue-body.js

import { readFile } from "node:fs/promises";
import { setFailed } from "@actions/core";
import yaml from "js-yaml";

function normalizeNewLines(str) {
  return str.replace(/\r\n/g, "\n");
}

function splitList(str) {
  let list = str.split(",");
  for (let i = 0; i < list.length; i++) {
    list[i] = list[i].trim();
  }

  if (list.length == 1 && list[0] == "") {
    return [];
  }
  return list;
}

/**
 * converts strings to their boolean - handles "true" and "True"
 * @param {string} str string to convert
 * @returns {boolean}
 */
function cleanBoolean(str) {
  if (str === "true" || str === "True") {
    return true;
  } else if (str === "false" || "False") {
    return false;
  } else {
    setFailed("issue parsing booleans" + error.message);
  }
}

/**
 * creates a list of fields from the issue template
 * @param {string} githubIssueTemplateFile file name
 * @returns {{type: string, id: string, attributes: {}, validations: {}}[]} array of filed objects
 */
async function parseFields(githubIssueTemplateFile) {
  try {
    let issueTemplate = await readFile(githubIssueTemplateFile, "utf8");
    let githubFormData = yaml.load(issueTemplate);

    // Markdown fields aren’t included in output body
    let fields = githubFormData.body.filter(
      (field) => field.type !== "markdown"
    );
    console.log("got ", fields.length, " fields", fields);
    return fields;
  } catch (error) {
    setFailed(
      "could not parse the issue template, please report to developers" +
        error.message
    );
  }
}

/**
 * converts the body to an array to be matched with the fields
 * @param {string} body from the issue payload
 * @returns {string[]} array of the values found in the issue, if no value was inputted and no default configured, will be empty string
 */
function parseBodyData(body) {
  // Warning: this will likely not handle new lines in a textarea field input
  try {
    let bodyData = normalizeNewLines(body)
      .split("\n")
      .filter((entry) => {
        return !!entry && !entry.startsWith("###");
      })
      .map((entry) => {
        entry = entry.trim();

        return entry === "_No response_" ? "" : entry;
      });
    console.log("got form body with length ", bodyData.length, bodyData);

    return bodyData;
  } catch (error) {
    setFailed(
      "could not parse the issue, please make sure you followed all instructions in the template" +
        error.message
    );
  }
}

/**
 * matches field ids to the corresponding body data
 * @param {{type: string, id: string, attributes: {}, validations: {}}[]} fields
 * @param {string[]} bodyData
 * @returns {{[id: string] : [value: string]}} id/value pairs for the issue, ready to be converted into the expected OpenPATH config
 */
function parseCombined(fields, bodyData) {
  //map fields and entries to an object, then we map that
  try {
    let returnObject = {};
    for (let j = 0, k = bodyData.length; j < k; j++) {
      //skip matching if the field does not exist
      if (!fields[j]) {
        continue;
      }
      let entry = bodyData[j];
      returnObject[fields[j].id] = entry;
    }
    console.log("combined form and body to get", returnObject);
    return returnObject;
  } catch {
    setFailed(
      "error matching the template to the issue bode, are there missing fields?" +
        error.message
    );
  }
}

/**
 * pulls the survey section from the data
 * @param {{[id: string] : [value: string]}} dataObject id/value pairs for the issue
 * @returns {{surveys:{}, trip-labels: string}} the survey info section for this config
 */
function getSurveyInfo(dataObject) {
  console.log("constructing survey info");
  let surveyInfo = {};

  try {
    //demographics survey settings
    if (dataObject.survey_form_path) {
      surveyInfo.surveys = {
        UserProfileSurvey: {
          formPath: "json/demo-survey-v2.json",
          version: 1,
          compatibleWith: 1,
          dataKey: "manual/demographic_survey",
          labelTemplate: {
            en: "Answered",
            es: "Contestada",
          },
        },
      };
    } else {
      surveyInfo.surveys = {
        UserProfileSurvey: {
          formPath:
            "https://raw.githubusercontent.com/e-mission/nrel-openpath-deploy-configs/main/survey_resources/" +
            dataObject.url_abbreviation+
            "/" +
            dataObject.custom_dem_survey_path,
          version: 1,
          compatibleWith: 1,
          dataKey: "manual/demographic_survey",
          labelTemplate: {
            en: dataObject.labelTemplate_lang1.split("-")[1].trim(),
            es: dataObject.labelTemplate_lang2.split("-")[1].trim(),
          },
        },
      };
    }

    //labeling options
    if (dataObject.label_form_path) {
      surveyInfo["trip-labels"] = "MULTILABEL";
    } else if (dataObject.label_options && dataObject.label_options != "") {
      surveyInfo["trip-labels"] = "MULTILABEL"; //label_options goes outside of this?
    } else {
      //TODO determine proceedure for custom label surveys
      surveyInfo["trip-labels"] = "ENKETO";
    }

    return surveyInfo;
  } catch (error) {
    setFailed(
      "Problem with the surveys, please make sure you filled out the survey and label related fields according to the directions" +
        error.message
    );
  }
}

/**
 * gets the template_text object for a single language
 * @param {string} language_key either '_lang1' or '_lang2'
 * @param {{[id: string] : [value: string]}} dataObject id/value pairs for the issue
 * @returns {{}} object for one language's section in template_text
 */
function getTextForLanguage(language_key, dataObject) {
  const textKeys = [
    "deployment_partner_name",
    "deployment_name",
    "summary_line_1",
    "summary_line_2",
    "summary_line_3",
    "short_textual_description",
    "why_we_collect",
  ];
  try {
    let languageText = {};
    for (let i = 0; i < textKeys.length; i++) {
      languageText[textKeys[i]] = dataObject[textKeys[i] + language_key];
    }

    let researchQuestions = [
      dataObject["research_question_1" + language_key],
      dataObject["research_question_2" + language_key],
      dataObject["research_question_3" + language_key],
    ];

    let blank = true;
    for (let i = 0; i < researchQuestions.length; i++) {
      if (researchQuestions[i] != "") {
        blank = false;
      }
    }
    if (!blank) {
      languageText.research_questions = researchQuestions;
    } else {
      languageText.research_questions = [];
    }

    return languageText;
  } catch (error) {
    setFailed(
      "error parsing template text for " + language_key + error.message
    );
  }
}

/**
 * gets the translated text section from the data
 * @param {{[id: string] : [value: string]}} dataObject id/value pairs for the issue
 * @returns {{}} template_text object for this config, will have either 1 or 2 languages
 */
function getTranslatedText(dataObject) {
  let translatedText = {};
  try {
    translatedText[dataObject["lang_1"]] = getTextForLanguage(
      "_lang1",
      dataObject
    );

    if (dataObject.lang_2 != "None") {
      translatedText[dataObject["lang_2"]] = getTextForLanguage(
        "_lang2",
        dataObject
      );
    }

    return translatedText;
  } catch (error) {
    setFailed("problem with the templated text" + error.message);
  }
}

/**
 * fields are from the issue template
 * bodyData is from the filled out issue
 * @param {*} githubIssueTemplateFile - the issue template that created this request
 * @param {*} body - body of the issue for this request
 * @returns an object for the config file, formatted as existing files in repo are
 */
export async function parseIssueBody(githubIssueTemplateFile, body) {
  //first handle the input, combined object for key/value pairs
  let fields = await parseFields(githubIssueTemplateFile);
  let bodyData = parseBodyData(body);
  let combinedObject = parseCombined(fields, bodyData);

  // must be lower case
  combinedObject.url_abbreviation = combinedObject.url_abbreviation.toLowerCase();

  //then compose the config object
  let configObject = {};
  try {
    configObject["url_abbreviation"] = combinedObject.url_abbreviation;
    configObject["version"] = 1;
    configObject["ts"] = Math.floor(Date.now() / 1000);

    let connect_url =
      "https://" + combinedObject.url_abbreviation + "-openpath.nrel.gov/api/";
    configObject["server"] = {
      connectUrl: connect_url,
      aggregate_call_auth: "user_only",
    }; //TODO check options for call + add to form?

    let subgroups = combinedObject.subgroups.split(",").map(item => item.trim());
    if (subgroups.length == 1 && subgroups[0] == "") {
      subgroups = ["default", "test"];
    }
    configObject["opcode"] = {
      autogen: cleanBoolean(combinedObject.autogen),
      subgroups: subgroups,
    };

    let textObject = getTranslatedText(combinedObject);
    configObject["intro"] = {
      program_or_study: combinedObject.program_or_study,
      start_month: combinedObject.start.split("/")[0],
      start_year: combinedObject.start.split("/")[1],
      mode_studied: combinedObject.mode_studied,
      program_admin_email: combinedObject.program_admin_email,
      program_admin_contact: combinedObject.program_admin_contact,
      deployment_partner_name: combinedObject.deployment_partner_name_lang1,
      translated_text: textObject,
    };

    configObject["survey_info"] = getSurveyInfo(combinedObject);
    if (combinedObject.label_options) {
      configObject.label_options =
        "https://raw.githubusercontent.com/e-mission/nrel-openpath-deploy-configs/main/label_options/" +
        combinedObject.label_options;
    }
    //TODO: add handling for custom trip surveys

    configObject["display_config"] = {
      use_imperial: cleanBoolean(combinedObject.use_imperial),
    };
    configObject["metrics"] = {
      include_test_users: cleanBoolean(combinedObject.include_test_users),
    };
    configObject["profile_controls"] = {
      support_upload: false,
      trip_end_notification: cleanBoolean(combinedObject.trip_end_notification),
    };

    configObject["admin_dashboard"] = {
      data_trips_columns_exclude: splitList(
        combinedObject.data_trips_columns_exclude
      ),
      additional_trip_columns: splitList(
        combinedObject.additional_trip_columns
      ),
      data_uuids_columns_exclude: splitList(
        combinedObject.data_uuids_columns_exclude
      ),
      //unlikely to not be nrelop, could require manual changes
      token_prefix: "nrelop",
      token_generate: !configObject['opcode']['autogen'], // only for pregen tokens
    };

    //list of all the boolean values in the admin dashboard section, add to issue template and list for new value
    let ADMIN_LIST = [
      "overview_users",
      "overview_active_users",
      "overview_trips",
      "overview_signup_trends",
      "overview_trips_trend",
      "data_uuids",
      "data_trips",
      "map_heatmap",
      "map_bubble",
      "map_trip_lines",
      "options_uuids",
      "options_emails",
    ];

    for (let i = 0; i < ADMIN_LIST.length; i++) {
      configObject["admin_dashboard"][ADMIN_LIST[i]] = cleanBoolean(
        combinedObject[ADMIN_LIST[i]]
      );
    }

    //list of administrator emails
    let email_list = combinedObject.admin_access.split(',');
    if (email_list.length > 5){
      setFailed("sorry, admin access is limited to a maximum of 5 emails, please shorten your list of emails"); 
    }
    // leading/trailing whitespace will lead to errors
    for (let i = 0; i < email_list.length; i++) {
      email_list[i] = email_list[i].trim();
    }
    configObject['admin_dashboard'].admin_access = email_list;

    //TODO: add handling for custom reminder schemes

    console.log(configObject);
    return configObject;
  } catch (error) {
    setFailed(
      "Issue parsing the form you submitted into a config, please ensure you followed all instructions" +
        error.message
    );
  }
}
